// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface IBudgetController {
    function budgetLimitWad(address agent) external view returns (uint256);
}

/// @notice Settles metered LLM energy costs while enforcing PID budgets per epoch.
contract AgentSettlementVault is AccessControl, EIP712, ReentrancyGuard {
    using SafeERC20 for IERC20;

    bytes32 public constant SETTLER_ROLE = keccak256("SETTLER_ROLE");
    bytes32 public constant ATTESTOR_ROLE = keccak256("ATTESTOR_ROLE");
    bytes32 public constant USAGE_RECEIPT_TYPEHASH = keccak256(
        "UsageReceipt(address agent,address beneficiary,bytes32 providerRequestId,bytes32 modelId,"
        "bytes32 tariffId,bytes32 responseHash,uint256 promptTokens,uint256 completionTokens,uint256 energyKwhWad,"
        "uint256 amountWad,uint256 usageTimestamp,uint256 usageEpoch,uint256 nonce,uint256 deadline)"
    );

    struct UsageReceipt {
        address agent;
        address beneficiary;
        bytes32 providerRequestId;
        bytes32 modelId;
        bytes32 tariffId;
        bytes32 responseHash;
        uint256 promptTokens;
        uint256 completionTokens;
        uint256 energyKwhWad;
        uint256 amountWad;
        uint256 usageTimestamp;
        uint256 usageEpoch;
        uint256 nonce;
        uint256 deadline;
    }

    IERC20 public immutable settlementToken;
    IBudgetController public immutable budgetController;
    uint64 public immutable epochDuration;
    uint64 public immutable maximumUsageAge;

    mapping(address agent => mapping(uint256 epoch => uint256 amountWad)) public spentWad;
    mapping(bytes32 usageDigest => bool settled) public settledUsage;

    error InvalidConfiguration();
    error InvalidAttestor(address signer);
    error InvalidUsageEpoch(uint256 supplied, uint256 expected);
    error InvalidUsageTime();
    error DuplicateUsage(bytes32 usageDigest);
    error BudgetExceeded(uint256 requestedWad, uint256 remainingWad);

    event UsageSettled(
        bytes32 indexed usageDigest,
        address indexed agent,
        address indexed beneficiary,
        uint256 amountWad,
        uint256 epoch
    );

    constructor(
        address admin,
        IERC20 token,
        IBudgetController controller,
        uint64 epochDurationSeconds,
        uint64 maximumUsageAgeSeconds
    )
        EIP712("AgentSettlementVault", "1")
    {
        if (
            admin == address(0) || address(token) == address(0) ||
            address(controller) == address(0) || epochDurationSeconds == 0 ||
            maximumUsageAgeSeconds == 0
        ) revert InvalidConfiguration();
        settlementToken = token;
        budgetController = controller;
        epochDuration = epochDurationSeconds;
        maximumUsageAge = maximumUsageAgeSeconds;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ATTESTOR_ROLE, admin);
    }

    function settle(UsageReceipt calldata receipt, bytes calldata signature)
        external
        onlyRole(SETTLER_ROLE)
        nonReentrant
    {
        if (
            receipt.agent == address(0) || receipt.beneficiary == address(0) ||
            receipt.providerRequestId == bytes32(0) || receipt.modelId == bytes32(0) ||
            receipt.tariffId == bytes32(0) || receipt.responseHash == bytes32(0)
        ) {
            revert InvalidConfiguration();
        }
        if (
            receipt.usageTimestamp > block.timestamp || receipt.deadline < receipt.usageTimestamp ||
            receipt.deadline - receipt.usageTimestamp > maximumUsageAge ||
            block.timestamp > receipt.deadline
        ) {
            revert InvalidUsageTime();
        }
        uint256 expectedEpoch = receipt.usageTimestamp / epochDuration;
        if (receipt.usageEpoch != expectedEpoch) {
            revert InvalidUsageEpoch(receipt.usageEpoch, expectedEpoch);
        }

        bytes32 usageDigest = hashUsageReceipt(receipt);
        address signer = ECDSA.recover(usageDigest, signature);
        if (!hasRole(ATTESTOR_ROLE, signer)) revert InvalidAttestor(signer);
        if (settledUsage[usageDigest]) revert DuplicateUsage(usageDigest);
        uint256 budget = budgetController.budgetLimitWad(receipt.agent);
        uint256 alreadySpent = spentWad[receipt.agent][receipt.usageEpoch];
        uint256 remaining = alreadySpent >= budget ? 0 : budget - alreadySpent;
        if (receipt.amountWad == 0 || receipt.amountWad > remaining) {
            revert BudgetExceeded(receipt.amountWad, remaining);
        }

        settledUsage[usageDigest] = true;
        spentWad[receipt.agent][receipt.usageEpoch] = alreadySpent + receipt.amountWad;
        settlementToken.safeTransfer(receipt.beneficiary, receipt.amountWad);
        emit UsageSettled(
            usageDigest,
            receipt.agent,
            receipt.beneficiary,
            receipt.amountWad,
            receipt.usageEpoch
        );
    }

    function hashUsageReceipt(UsageReceipt calldata receipt) public view returns (bytes32) {
        // UsageReceipt contains only static ABI types; encoding the tuple is identical to
        // encoding each member in declaration order and avoids compiler stack exhaustion.
        bytes32 structHash = keccak256(abi.encode(USAGE_RECEIPT_TYPEHASH, receipt));
        return _hashTypedDataV4(structHash);
    }
}
