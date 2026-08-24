// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {AgentSettlementVault} from "../contracts/AgentSettlementVault.sol";
import {EuroSettlementToken} from "../contracts/EuroSettlementToken.sol";
import {PIDBudgetController} from "../contracts/PIDBudgetController.sol";
import {ReversibleRandomTimelock} from "../contracts/ReversibleRandomTimelock.sol";

/// @notice Explicit second deployment phase, run only after governance accepts the handoff.
contract FinalizeHandoff is Script {
    error GovernanceNotReady();

    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);
        address governance = vm.envAddress("GOVERNANCE_ADDRESS");
        address proposer = vm.envAddress("PROPOSER_ADDRESS");
        address canceller = vm.envAddress("CANCELLER_ADDRESS");
        address executor = vm.envAddress("EXECUTOR_ADDRESS");
        address riskPauser = vm.envAddress("RISK_PAUSER_ADDRESS");
        address attestor = vm.envAddress("METERING_ATTESTOR_ADDRESS");
        address velocityOracle = vm.envAddress("VELOCITY_ORACLE_ADDRESS");
        EuroSettlementToken token = EuroSettlementToken(vm.envAddress("TOKEN_ADDRESS"));
        PIDBudgetController controller = PIDBudgetController(vm.envAddress("PID_CONTROLLER_ADDRESS"));
        AgentSettlementVault vault = AgentSettlementVault(vm.envAddress("VAULT_ADDRESS"));
        ReversibleRandomTimelock timelock =
            ReversibleRandomTimelock(vm.envAddress("TIMELOCK_ADDRESS"));

        if (
            governance == address(0) || governance == deployer ||
            proposer == deployer || canceller == deployer || executor == deployer ||
            attestor == deployer || velocityOracle == deployer ||
            !token.hasRole(token.DEFAULT_ADMIN_ROLE(), governance) ||
            !token.hasRole(token.ISSUER_ROLE(), governance) ||
            !token.hasRole(token.COMPLIANCE_ROLE(), governance) ||
            !token.hasRole(token.PAUSER_ROLE(), governance) ||
            !controller.hasRole(controller.DEFAULT_ADMIN_ROLE(), governance) ||
            !controller.hasRole(controller.ORACLE_ROLE(), velocityOracle) ||
            !vault.hasRole(vault.DEFAULT_ADMIN_ROLE(), governance) ||
            !vault.hasRole(vault.PAUSER_ROLE(), riskPauser) ||
            !timelock.hasRole(timelock.DEFAULT_ADMIN_ROLE(), governance) ||
            !vault.hasRole(vault.ATTESTOR_ROLE(), attestor) ||
            !timelock.hasRole(timelock.PROPOSER_ROLE(), proposer) ||
            !timelock.hasRole(timelock.CANCELLER_ROLE(), canceller) ||
            !timelock.hasRole(timelock.EXECUTOR_ROLE(), executor)
        ) revert GovernanceNotReady();

        vm.startBroadcast(deployerKey);
        token.renounceRole(token.ISSUER_ROLE(), deployer);
        token.renounceRole(token.COMPLIANCE_ROLE(), deployer);
        token.renounceRole(token.PAUSER_ROLE(), deployer);
        token.renounceRole(token.DEFAULT_ADMIN_ROLE(), deployer);
        controller.renounceRole(controller.DEFAULT_ADMIN_ROLE(), deployer);
        vault.renounceRole(vault.ATTESTOR_ROLE(), deployer);
        vault.renounceRole(vault.PAUSER_ROLE(), deployer);
        vault.renounceRole(vault.DEFAULT_ADMIN_ROLE(), deployer);
        timelock.renounceRole(timelock.PROPOSER_ROLE(), deployer);
        timelock.renounceRole(timelock.CANCELLER_ROLE(), deployer);
        timelock.renounceRole(timelock.EXECUTOR_ROLE(), deployer);
        timelock.renounceRole(timelock.DEFAULT_ADMIN_ROLE(), deployer);
        vm.stopBroadcast();
    }
}
