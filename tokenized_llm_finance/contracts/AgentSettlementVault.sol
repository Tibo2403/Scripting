// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface IBudgetController {
    function budgetLimitWad(address agent) external view returns (uint256);
}

/// @notice Settles metered LLM energy costs while enforcing PID budgets per epoch.
contract AgentSettlementVault is AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;

    bytes32 public constant SETTLER_ROLE = keccak256("SETTLER_ROLE");

    IERC20 public immutable settlementToken;
    IBudgetController public immutable budgetController;
    uint64 public immutable epochDuration;

    mapping(address agent => mapping(uint256 epoch => uint256 amountWad)) public spentWad;
    mapping(bytes32 usageDigest => bool settled) public settledUsage;

    error InvalidConfiguration();
    error DuplicateUsage(bytes32 usageDigest);
    error BudgetExceeded(uint256 requestedWad, uint256 remainingWad);

    event UsageSettled(
        bytes32 indexed usageDigest,
        address indexed agent,
        address indexed beneficiary,
        uint256 amountWad,
        uint256 epoch
    );

    constructor(address admin, IERC20 token, IBudgetController controller, uint64 epochDurationSeconds) {
        if (
            admin == address(0) || address(token) == address(0) ||
            address(controller) == address(0) || epochDurationSeconds == 0
        ) revert InvalidConfiguration();
        settlementToken = token;
        budgetController = controller;
        epochDuration = epochDurationSeconds;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    function settle(address agent, address beneficiary, uint256 amountWad, bytes32 usageDigest)
        external
        onlyRole(SETTLER_ROLE)
        nonReentrant
    {
        if (settledUsage[usageDigest]) revert DuplicateUsage(usageDigest);
        uint256 epoch = block.timestamp / epochDuration;
        uint256 budget = budgetController.budgetLimitWad(agent);
        uint256 alreadySpent = spentWad[agent][epoch];
        uint256 remaining = alreadySpent >= budget ? 0 : budget - alreadySpent;
        if (amountWad > remaining) revert BudgetExceeded(amountWad, remaining);

        settledUsage[usageDigest] = true;
        spentWad[agent][epoch] = alreadySpent + amountWad;
        settlementToken.safeTransfer(beneficiary, amountWad);
        emit UsageSettled(usageDigest, agent, beneficiary, amountWad, epoch);
    }
}
