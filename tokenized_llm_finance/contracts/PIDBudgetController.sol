// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {SignedWadMath} from "./libraries/SignedWadMath.sol";

/// @notice Adjusts an agent's EUR-denominated WAD budget from observed network velocity.
/// @dev All velocities, gains, outputs and budgets use 1e18 fixed point. Time uses exact seconds.
contract PIDBudgetController is AccessControl {
    using SignedWadMath for int256;

    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");
    uint256 public constant MAXIMUM_GAIN_WAD = 100e18;
    uint64 public immutable minimumUpdateInterval;
    uint64 public immutable maximumElapsedTime;

    struct AgentPID {
        uint256 budgetLimitWad;
        uint256 minimumBudgetWad;
        uint256 maximumBudgetWad;
        uint256 targetVelocityWad;
        uint256 maximumVelocityWad;
        uint256 maximumBudgetChangeWad;
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

    struct AgentConfiguration {
        uint256 initialBudgetWad;
        uint256 minimumBudgetWad;
        uint256 maximumBudgetWad;
        uint256 targetVelocityWad;
        uint256 maximumVelocityWad;
        uint256 maximumBudgetChangeWad;
        uint256 kpWad;
        uint256 kiWad;
        uint256 kdWad;
        int256 integralMinimumWadSeconds;
        int256 integralMaximumWadSeconds;
    }

    mapping(address agent => AgentPID state) private _agents;

    error InvalidConfiguration();
    error AgentNotConfigured(address agent);
    error UpdateTooSoon();
    error ObservationStale();
    error ObservationOutsideRange(uint256 observed, uint256 maximum);

    event AgentConfigured(address indexed agent, uint256 initialBudgetWad, uint256 targetVelocityWad);
    event BudgetUpdated(
        address indexed agent,
        uint256 observedVelocityWad,
        int256 errorWad,
        int256 controllerOutputWad,
        uint256 budgetLimitWad
    );

    constructor(address admin, address oracle, uint64 minimumInterval, uint64 maximumElapsed) {
        if (
            admin == address(0) || oracle == address(0) || minimumInterval == 0 ||
            maximumElapsed < minimumInterval
        ) revert InvalidConfiguration();
        minimumUpdateInterval = minimumInterval;
        maximumElapsedTime = maximumElapsed;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ORACLE_ROLE, oracle);
    }

    function configureAgent(address agent, AgentConfiguration calldata config)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (
            agent == address(0) || config.minimumBudgetWad > config.initialBudgetWad ||
            config.initialBudgetWad > config.maximumBudgetWad ||
            config.integralMinimumWadSeconds > 0 || config.integralMaximumWadSeconds < 0 ||
            !_fitsSigned(config.maximumBudgetWad) || !_fitsSigned(config.maximumVelocityWad) ||
            config.targetVelocityWad > config.maximumVelocityWad ||
            config.maximumVelocityWad == 0 || config.maximumBudgetChangeWad == 0 ||
            config.maximumBudgetChangeWad > config.maximumBudgetWad - config.minimumBudgetWad ||
            config.kpWad > MAXIMUM_GAIN_WAD || config.kiWad > MAXIMUM_GAIN_WAD ||
            config.kdWad > MAXIMUM_GAIN_WAD ||
            config.maximumVelocityWad > uint256(type(int256).max) / maximumElapsedTime
        ) revert InvalidConfiguration();

        AgentPID storage pid = _agents[agent];
        pid.budgetLimitWad = config.initialBudgetWad;
        pid.minimumBudgetWad = config.minimumBudgetWad;
        pid.maximumBudgetWad = config.maximumBudgetWad;
        pid.targetVelocityWad = config.targetVelocityWad;
        pid.maximumVelocityWad = config.maximumVelocityWad;
        pid.maximumBudgetChangeWad = config.maximumBudgetChangeWad;
        pid.kpWad = config.kpWad;
        pid.kiWad = config.kiWad;
        pid.kdWad = config.kdWad;
        pid.integralErrorWadSeconds = 0;
        pid.previousErrorWad = 0;
        pid.integralMinimumWadSeconds = config.integralMinimumWadSeconds;
        pid.integralMaximumWadSeconds = config.integralMaximumWadSeconds;
        pid.lastUpdate = uint64(block.timestamp);
        pid.configured = true;
        emit AgentConfigured(agent, config.initialBudgetWad, config.targetVelocityWad);
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
        if (observedVelocityWad > pid.maximumVelocityWad) {
            revert ObservationOutsideRange(observedVelocityWad, pid.maximumVelocityWad);
        }

        uint256 elapsed = block.timestamp - pid.lastUpdate;
        if (elapsed < minimumUpdateInterval) revert UpdateTooSoon();
        if (elapsed > maximumElapsedTime) revert ObservationStale();

        int256 errorWad = int256(pid.targetVelocityWad) - int256(observedVelocityWad);
        int256 integrated = pid.integralErrorWadSeconds + errorWad * int256(elapsed);
        integrated = integrated.clamp(pid.integralMinimumWadSeconds, pid.integralMaximumWadSeconds);
        int256 derivativeWad = (errorWad - pid.previousErrorWad) / int256(elapsed);

        int256 outputWad = errorWad.mulWad(pid.kpWad)
            + integrated.mulWad(pid.kiWad)
            + derivativeWad.mulWad(pid.kdWad);
        int256 limitedOutput = outputWad.clamp(
            -int256(pid.maximumBudgetChangeWad), int256(pid.maximumBudgetChangeWad)
        );
        uint256 nextBudget;
        if (limitedOutput >= 0) {
            uint256 increase = uint256(limitedOutput);
            nextBudget = increase > pid.maximumBudgetWad - pid.budgetLimitWad
                ? pid.maximumBudgetWad
                : pid.budgetLimitWad + increase;
        } else {
            uint256 decrease = uint256(-limitedOutput);
            nextBudget = decrease > pid.budgetLimitWad - pid.minimumBudgetWad
                ? pid.minimumBudgetWad
                : pid.budgetLimitWad - decrease;
        }

        pid.budgetLimitWad = nextBudget;
        pid.integralErrorWadSeconds = integrated;
        pid.previousErrorWad = errorWad;
        pid.lastUpdate = uint64(block.timestamp);

        emit BudgetUpdated(agent, observedVelocityWad, errorWad, limitedOutput, pid.budgetLimitWad);
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
