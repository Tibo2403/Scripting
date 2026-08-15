// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/// @notice Permissioned directory of banks admitted to the settlement network.
contract BankRegistry is AccessControl {
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");
    bytes32 public constant SUSPENDER_ROLE = keccak256("SUSPENDER_ROLE");

    struct Bank {
        bytes32 bicHash;
        address settlementAccount;
        uint64 registeredAt;
        bool active;
    }

    mapping(bytes32 bankId => Bank bank) private _banks;
    mapping(address settlementAccount => bytes32 bankId) public bankIdBySettlementAccount;

    error InvalidBank();
    error BankAlreadyRegistered(bytes32 bankId);
    error BankNotRegistered(bytes32 bankId);
    error SettlementAccountAlreadyUsed(address account);
    error BankSuspended(bytes32 bankId);

    event BankRegistered(
        bytes32 indexed bankId,
        bytes32 indexed bicHash,
        address indexed settlementAccount
    );
    event SettlementAccountChanged(
        bytes32 indexed bankId,
        address indexed previousAccount,
        address indexed newAccount
    );
    event BankStatusChanged(bytes32 indexed bankId, bool active);

    constructor(address admin) {
        if (admin == address(0)) revert InvalidBank();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REGISTRAR_ROLE, admin);
        _grantRole(SUSPENDER_ROLE, admin);
    }

    function registerBank(
        bytes32 bankId,
        bytes32 bicHash,
        address account
    ) external onlyRole(REGISTRAR_ROLE) {
        if (bankId == bytes32(0) || bicHash == bytes32(0) || account == address(0)) {
            revert InvalidBank();
        }
        if (_banks[bankId].settlementAccount != address(0)) {
            revert BankAlreadyRegistered(bankId);
        }
        if (bankIdBySettlementAccount[account] != bytes32(0)) {
            revert SettlementAccountAlreadyUsed(account);
        }

        _banks[bankId] = Bank({
            bicHash: bicHash,
            settlementAccount: account,
            registeredAt: uint64(block.timestamp),
            active: true
        });
        bankIdBySettlementAccount[account] = bankId;

        emit BankRegistered(bankId, bicHash, account);
    }

    function changeSettlementAccount(
        bytes32 bankId,
        address newAccount
    ) external onlyRole(REGISTRAR_ROLE) {
        Bank storage bank = _registeredBank(bankId);
        if (newAccount == address(0)) revert InvalidBank();
        if (bankIdBySettlementAccount[newAccount] != bytes32(0)) {
            revert SettlementAccountAlreadyUsed(newAccount);
        }

        address previousAccount = bank.settlementAccount;
        delete bankIdBySettlementAccount[previousAccount];
        bank.settlementAccount = newAccount;
        bankIdBySettlementAccount[newAccount] = bankId;

        emit SettlementAccountChanged(bankId, previousAccount, newAccount);
    }

    function setBankActive(bytes32 bankId, bool active) external onlyRole(SUSPENDER_ROLE) {
        Bank storage bank = _registeredBank(bankId);
        bank.active = active;
        emit BankStatusChanged(bankId, active);
    }

    function getBank(bytes32 bankId) external view returns (Bank memory) {
        Bank memory bank = _banks[bankId];
        if (bank.settlementAccount == address(0)) revert BankNotRegistered(bankId);
        return bank;
    }

    function settlementAccount(bytes32 bankId) external view returns (address) {
        return _registeredBank(bankId).settlementAccount;
    }

    function requireActiveBank(bytes32 bankId) external view returns (address) {
        Bank storage bank = _registeredBank(bankId);
        if (!bank.active) revert BankSuspended(bankId);
        return bank.settlementAccount;
    }

    function _registeredBank(bytes32 bankId) private view returns (Bank storage bank) {
        bank = _banks[bankId];
        if (bank.settlementAccount == address(0)) revert BankNotRegistered(bankId);
    }
}
