// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";

import {AgentSettlementVault} from "../contracts/AgentSettlementVault.sol";
import {EuroSettlementToken} from "../contracts/EuroSettlementToken.sol";
import {PIDBudgetController} from "../contracts/PIDBudgetController.sol";
import {ReversibleRandomTimelock} from "../contracts/ReversibleRandomTimelock.sol";

contract Deploy is Script {
    function run() external returns (
        EuroSettlementToken token,
        PIDBudgetController controller,
        AgentSettlementVault vault,
        ReversibleRandomTimelock timelock
    ) {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);
        address governance = vm.envAddress("GOVERNANCE_ADDRESS");
        address supervisor = vm.envAddress("SUPERVISOR_ADDRESS");
        address velocityOracle = vm.envAddress("VELOCITY_ORACLE_ADDRESS");

        vm.startBroadcast(deployerKey);
        token = new EuroSettlementToken(deployer);
        controller = new PIDBudgetController(deployer, velocityOracle);
        vault = new AgentSettlementVault(
            deployer, token, controller, uint64(vm.envUint("BUDGET_EPOCH_SECONDS"))
        );
        timelock = new ReversibleRandomTimelock(
            deployer,
            vm.envAddress("VRF_COORDINATOR_ADDRESS"),
            vm.envUint("VRF_SUBSCRIPTION_ID"),
            vm.envBytes32("VRF_KEY_HASH"),
            uint64(vm.envUint("MINIMUM_DELAY_SECONDS")),
            uint64(vm.envUint("NOISE_WINDOW_SECONDS")),
            uint16(vm.envUint("VRF_CONFIRMATIONS")),
            uint32(vm.envUint("VRF_CALLBACK_GAS_LIMIT"))
        );

        token.setAllowed(address(vault), true);
        vault.grantRole(vault.SETTLER_ROLE(), address(timelock));
        timelock.setTargetAllowed(address(vault), true);

        token.grantRole(token.DEFAULT_ADMIN_ROLE(), governance);
        token.grantRole(token.ISSUER_ROLE(), governance);
        token.grantRole(token.COMPLIANCE_ROLE(), governance);
        token.grantRole(token.PAUSER_ROLE(), governance);
        controller.grantRole(controller.DEFAULT_ADMIN_ROLE(), governance);
        vault.grantRole(vault.DEFAULT_ADMIN_ROLE(), governance);
        timelock.grantRole(timelock.DEFAULT_ADMIN_ROLE(), governance);
        timelock.grantRole(timelock.PROPOSER_ROLE(), supervisor);
        timelock.grantRole(timelock.CANCELLER_ROLE(), supervisor);
        timelock.grantRole(timelock.EXECUTOR_ROLE(), supervisor);

        if (governance != deployer) {
            token.renounceRole(token.ISSUER_ROLE(), deployer);
            token.renounceRole(token.COMPLIANCE_ROLE(), deployer);
            token.renounceRole(token.PAUSER_ROLE(), deployer);
            token.renounceRole(token.DEFAULT_ADMIN_ROLE(), deployer);
            controller.renounceRole(controller.DEFAULT_ADMIN_ROLE(), deployer);
            vault.renounceRole(vault.DEFAULT_ADMIN_ROLE(), deployer);
            timelock.renounceRole(timelock.PROPOSER_ROLE(), deployer);
            timelock.renounceRole(timelock.CANCELLER_ROLE(), deployer);
            timelock.renounceRole(timelock.EXECUTOR_ROLE(), deployer);
            timelock.renounceRole(timelock.DEFAULT_ADMIN_ROLE(), deployer);
        }
        vm.stopBroadcast();
    }
}
