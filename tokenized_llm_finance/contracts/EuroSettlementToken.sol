// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @notice Permissioned private EUR-denominated settlement asset.
/// @dev This token does not represent central-bank money and does not imply ECB backing.
/// @dev Legal MiCA compliance, reserves, redemption and identity checks are off-chain obligations.
contract EuroSettlementToken is ERC20, AccessControl, Pausable {
    bytes32 public constant ISSUER_ROLE = keccak256("ISSUER_ROLE");
    bytes32 public constant COMPLIANCE_ROLE = keccak256("COMPLIANCE_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    mapping(address account => bool allowed) public isAllowed;

    error AccountNotAllowed(address account);
    error ZeroAddress();

    event ComplianceStatusChanged(address indexed account, bool allowed);

    constructor(address admin) ERC20("Euro Energy Settlement Token", "EEST") {
        if (admin == address(0)) revert ZeroAddress();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ISSUER_ROLE, admin);
        _grantRole(COMPLIANCE_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        isAllowed[admin] = true;
        emit ComplianceStatusChanged(admin, true);
    }

    function setAllowed(address account, bool allowed) external onlyRole(COMPLIANCE_ROLE) {
        if (account == address(0)) revert ZeroAddress();
        isAllowed[account] = allowed;
        emit ComplianceStatusChanged(account, allowed);
    }

    function mint(address to, uint256 amount) external onlyRole(ISSUER_ROLE) {
        _mint(to, amount);
    }

    function burn(uint256 amount) external {
        _burn(msg.sender, amount);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function _update(address from, address to, uint256 value) internal override whenNotPaused {
        if (from != address(0) && !isAllowed[from]) revert AccountNotAllowed(from);
        if (to != address(0) && !isAllowed[to]) revert AccountNotAllowed(to);
        super._update(from, to, value);
    }
}
