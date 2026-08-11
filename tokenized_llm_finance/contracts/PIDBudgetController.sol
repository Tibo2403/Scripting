// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {SignedWadMath} from "./libraries/SignedWadMath.sol";

/// @notice Adjusts an agent's EUR-denominated WAD budget from observed network velocity.
/// @dev All velocities, gains, outputs and budgets use 1e18 fixed point. Time uses exact seconds.
contract PIDBudgetController is AccessControl {
    using SignedWadMath for int256;

    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");

    struct AgentPID {
        uint256 budgetLimitWad;
        uint256 minimumBudgetWad;
        uint256 maximumBudgetWad;
        uint256 targetVelocityWad;
        uint256 kpWad;
        uint256 kiWad;
        uint256 kdWad;
        int256 integralErrorWadSeconds;
        int256 previousErrorWad;
        int256 integralMinimumWadSeconds;
        int256 integralMaximumWadSeconds;
        uint64 lastUpdate;
        bool configured;
    }

    mapping(address agent => AgentPID state) private _agents;

    error InvalidConfiguration();
    error AgentNotConfigured(address agent);
    error UpdateTooSoon();
    error ValueOutsideSignedRange();

    event AgentConfigured(address indexed agent, uint256 initialBudgetWad, uint256 targetVelocityWad);
    event BudgetUpdated(
        address indexed agent,
        uint256 observedVelocityWad,
        int256 errorWad,
        int256 controllerOutputWad,
        uint256 budgetLimitWad
    );

    constructor(address admin, address oracle) {
        if (admin == address(0) || oracle == address(0)) revert InvalidConfiguration();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ORACLE_ROLE, oracle);
    }

    function configureAgent(
        address agent,
        uint256 initialBudgetWad,
        uint256 minimumBudgetWad,
        uint256 maximumBudgetWad,
        uint256 targetVelocityWad,
        uint256 kpWad,
        uint256 kiWad,
        uint256 kdWad,
        int256 integralMinimumWadSeconds,
        int256 integralMaximumWadSeconds
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (
            agent == address(0) || minimumBudgetWad > initialBudgetWad ||
            initialBudgetWad > maximumBudgetWad || integralMinimumWadSeconds > 0 ||
            integralMaximumWadSeconds < 0 || !_fitsSigned(maximumBudgetWad) ||
            !_fitsSigned(targetVelocityWad)
        ) revert InvalidConfiguration();

        _agents[agent] = AgentPID({
            budgetLimitWad: initialBudgetWad,
            minimumBudgetWad: minimumBudgetWad,
            maximumBudgetWad: maximumBudgetWad,
            targetVelocityWad: targetVelocityWad,
            kpWad: kpWad,
            kiWad: kiWad,
            kdWad: kdWad,
            integralErrorWadSeconds: 0,
            previousErrorWad: 0,
            integralMinimumWadSeconds: integralMinimumWadSeconds,
            integralMaximumWadSeconds: integralMaximumWadSeconds,
            lastUpdate: uint64(block.timestamp),
            configured: true
        });
        emit AgentConfigured(agent, initialBudgetWad, targetVelocityWad);
    }

    /// @notice Applies u(t)=Kp*e(t)+Ki*integral(e dt)+Kd*de/dt.
    /// @dev Division rounds toward zero by Solidity definition; Math.mulDiv avoids intermediate loss.
    function updateBudget(address agent, uint256 observedVelocityWad)
        external
        onlyRole(ORACLE_ROLE)
        returns (uint256)
    {
        AgentPID storage pid = _agents[agent];
        if (!pid.configured) revert AgentNotConfigured(agent);
        if (!_fitsSigned(observedVelocityWad)) revert ValueOutsideSignedRange();

        uint256 elapsed = block.timestamp - pid.lastUpdate;
        if (elapsed == 0) revert UpdateTooSoon();

        int256 errorWad = int256(pid.targetVelocityWad) - int256(observedVelocityWad);
        int256 integrated = pid.integralErrorWadSeconds + errorWad * int256(elapsed);
        integrated = integrated.clamp(pid.integralMinimumWadSeconds, pid.integralMaximumWadSeconds);
        int256 derivativeWad = (errorWad - pid.previousErrorWad) / int256(elapsed);

        int256 outputWad = errorWad.mulWad(pid.kpWad)
            + integrated.mulWad(pid.kiWad)
            + derivativeWad.mulWad(pid.kdWad);
        int256 candidate = int256(pid.budgetLimitWad) + outputWad;
        int256 clamped = candidate.clamp(int256(pid.minimumBudgetWad), int256(pid.maximumBudgetWad));

        pid.budgetLimitWad = uint256(clamped);
        pid.integralErrorWadSeconds = integrated;
        pid.previousErrorWad = errorWad;
        pid.lastUpdate = uint64(block.timestamp);

        emit BudgetUpdated(agent, observedVelocityWad, errorWad, outputWad, pid.budgetLimitWad);
        return pid.budgetLimitWad;
    }

    function budgetLimitWad(address agent) external view returns (uint256) {
        AgentPID storage pid = _agents[agent];
        if (!pid.configured) revert AgentNotConfigured(agent);
        return pid.budgetLimitWad;
    }

    function agentState(address agent) external view returns (AgentPID memory) {
        return _agents[agent];
    }

    function _fitsSigned(uint256 value) private pure returns (bool) {
        return value <= uint256(type(int256).max);
    }
}
