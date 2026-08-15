// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

import {BankRegistry} from "./BankRegistry.sol";

/// @notice Bilateral interbank settlement in a permissioned private settlement asset.
/// @dev The settlement token is not central-bank money and does not imply ECB backing.
contract InterbankSettlement is AccessControl, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    bytes32 public constant LIQUIDITY_MANAGER_ROLE = keccak256("LIQUIDITY_MANAGER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    enum Status { None, Pending, Settled, Cancelled, Expired }

    struct Instruction {
        bytes32 debtorBankId;
        bytes32 creditorBankId;
        bytes32 referenceHash;
        address debtorAccount;
        address creditorAccount;
        uint256 amountWad;
        uint64 createdAt;
        uint64 expiresAt;
        Status status;
    }

    struct LiquidityLimit {
        uint256 amountWad;
        bool configured;
    }

    IERC20 public immutable settlementToken;
    BankRegistry public immutable bankRegistry;
    uint64 public immutable epochDuration;
    uint64 public immutable maxInstructionLifetime;

    mapping(bytes32 instructionId => Instruction instruction) private _instructions;
    mapping(bytes32 bankId => LiquidityLimit limit) public outgoingLimits;
    mapping(bytes32 bankId => mapping(uint256 epoch => uint256 amountWad)) public outgoingSpent;

    error InvalidConfiguration();
    error InvalidInstruction();
    error InstructionAlreadyExists(bytes32 instructionId);
    error InvalidInstructionStatus(bytes32 instructionId, Status status);
    error UnauthorizedBankAccount(address account);
    error ParticipantAccountChanged(bytes32 bankId);
    error InstructionNotExpired(bytes32 instructionId);
    error InstructionPastExpiry(bytes32 instructionId);
    error LiquidityLimitNotConfigured(bytes32 bankId);
    error LiquidityLimitExceeded(bytes32 bankId, uint256 limitWad, uint256 requestedWad);

    event OutgoingLimitSet(bytes32 indexed bankId, uint256 amountWad);
    event InstructionInitiated(
        bytes32 indexed instructionId,
        bytes32 indexed debtorBankId,
        bytes32 indexed creditorBankId,
        uint256 amountWad,
        bytes32 referenceHash,
        uint64 expiresAt
    );
    event InstructionSettled(
        bytes32 indexed instructionId,
        bytes32 indexed debtorBankId,
        bytes32 indexed creditorBankId,
        uint256 amountWad,
        uint256 epoch
    );
    event InstructionCancelled(bytes32 indexed instructionId, bytes32 indexed debtorBankId);
    event InstructionExpired(bytes32 indexed instructionId);

    constructor(
        address admin,
        IERC20 settlementToken_,
        BankRegistry bankRegistry_,
        uint64 epochDuration_,
        uint64 maxInstructionLifetime_
    ) {
        if (
            admin == address(0) ||
            address(settlementToken_) == address(0) ||
            address(bankRegistry_) == address(0) ||
            epochDuration_ == 0 ||
            maxInstructionLifetime_ == 0
        ) revert InvalidConfiguration();

        settlementToken = settlementToken_;
        bankRegistry = bankRegistry_;
        epochDuration = epochDuration_;
        maxInstructionLifetime = maxInstructionLifetime_;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(LIQUIDITY_MANAGER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
    }

    function setOutgoingLimit(
        bytes32 bankId,
        uint256 amountWad
    ) external onlyRole(LIQUIDITY_MANAGER_ROLE) {
        bankRegistry.settlementAccount(bankId);
        outgoingLimits[bankId] = LiquidityLimit({amountWad: amountWad, configured: true});
        emit OutgoingLimitSet(bankId, amountWad);
    }

    function initiate(
        bytes32 instructionId,
        bytes32 creditorBankId,
        uint256 amountWad,
        bytes32 referenceHash,
        uint64 expiresAt
    ) external whenNotPaused {
        bytes32 debtorBankId = bankRegistry.bankIdBySettlementAccount(msg.sender);
        if (debtorBankId == bytes32(0)) revert UnauthorizedBankAccount(msg.sender);
        if (
            instructionId == bytes32(0) ||
            creditorBankId == bytes32(0) ||
            creditorBankId == debtorBankId ||
            amountWad == 0 ||
            referenceHash == bytes32(0) ||
            expiresAt <= block.timestamp ||
            uint256(expiresAt) > block.timestamp + maxInstructionLifetime
        ) revert InvalidInstruction();
        if (_instructions[instructionId].status != Status.None) {
            revert InstructionAlreadyExists(instructionId);
        }

        address debtorAccount = bankRegistry.requireActiveBank(debtorBankId);
        address creditorAccount = bankRegistry.requireActiveBank(creditorBankId);
        if (debtorAccount != msg.sender) revert UnauthorizedBankAccount(msg.sender);

        _instructions[instructionId] = Instruction({
            debtorBankId: debtorBankId,
            creditorBankId: creditorBankId,
            referenceHash: referenceHash,
            debtorAccount: debtorAccount,
            creditorAccount: creditorAccount,
            amountWad: amountWad,
            createdAt: uint64(block.timestamp),
            expiresAt: expiresAt,
            status: Status.Pending
        });
        emit InstructionInitiated(
            instructionId,
            debtorBankId,
            creditorBankId,
            amountWad,
            referenceHash,
            expiresAt
        );
    }

    function acceptAndSettle(bytes32 instructionId) external nonReentrant whenNotPaused {
        Instruction storage instruction = _pendingInstruction(instructionId);
        if (block.timestamp >= instruction.expiresAt) revert InstructionPastExpiry(instructionId);
        if (msg.sender != instruction.creditorAccount) revert UnauthorizedBankAccount(msg.sender);

        address currentDebtor = bankRegistry.requireActiveBank(instruction.debtorBankId);
        address currentCreditor = bankRegistry.requireActiveBank(instruction.creditorBankId);
        if (currentDebtor != instruction.debtorAccount) {
            revert ParticipantAccountChanged(instruction.debtorBankId);
        }
        if (currentCreditor != instruction.creditorAccount) {
            revert ParticipantAccountChanged(instruction.creditorBankId);
        }

        uint256 epoch = currentEpoch();
        LiquidityLimit memory limit = outgoingLimits[instruction.debtorBankId];
        if (!limit.configured) revert LiquidityLimitNotConfigured(instruction.debtorBankId);
        uint256 nextSpent = outgoingSpent[instruction.debtorBankId][epoch] + instruction.amountWad;
        if (nextSpent > limit.amountWad) {
            revert LiquidityLimitExceeded(instruction.debtorBankId, limit.amountWad, nextSpent);
        }

        instruction.status = Status.Settled;
        outgoingSpent[instruction.debtorBankId][epoch] = nextSpent;
        settlementToken.safeTransferFrom(
            instruction.debtorAccount,
            instruction.creditorAccount,
            instruction.amountWad
        );
        emit InstructionSettled(
            instructionId,
            instruction.debtorBankId,
            instruction.creditorBankId,
            instruction.amountWad,
            epoch
        );
    }

    function cancel(bytes32 instructionId) external {
        Instruction storage instruction = _pendingInstruction(instructionId);
        address currentDebtor = bankRegistry.settlementAccount(instruction.debtorBankId);
        if (msg.sender != instruction.debtorAccount && msg.sender != currentDebtor) {
            revert UnauthorizedBankAccount(msg.sender);
        }
        instruction.status = Status.Cancelled;
        emit InstructionCancelled(instructionId, instruction.debtorBankId);
    }

    function expire(bytes32 instructionId) external {
        Instruction storage instruction = _pendingInstruction(instructionId);
        if (block.timestamp < instruction.expiresAt) revert InstructionNotExpired(instructionId);
        instruction.status = Status.Expired;
        emit InstructionExpired(instructionId);
    }

    function pause() external onlyRole(PAUSER_ROLE) { _pause(); }
    function unpause() external onlyRole(PAUSER_ROLE) { _unpause(); }

    function currentEpoch() public view returns (uint256) {
        return block.timestamp / epochDuration;
    }

    function remainingOutgoingLimit(bytes32 bankId) external view returns (uint256) {
        LiquidityLimit memory limit = outgoingLimits[bankId];
        if (!limit.configured) revert LiquidityLimitNotConfigured(bankId);
        uint256 spent = outgoingSpent[bankId][currentEpoch()];
        return spent >= limit.amountWad ? 0 : limit.amountWad - spent;
    }

    function getInstruction(bytes32 instructionId) external view returns (Instruction memory) {
        Instruction memory instruction = _instructions[instructionId];
        if (instruction.status == Status.None) {
            revert InvalidInstructionStatus(instructionId, Status.None);
        }
        return instruction;
    }

    function _pendingInstruction(
        bytes32 instructionId
    ) private view returns (Instruction storage instruction) {
        instruction = _instructions[instructionId];
        if (instruction.status != Status.Pending) {
            revert InvalidInstructionStatus(instructionId, instruction.status);
        }
    }
}
