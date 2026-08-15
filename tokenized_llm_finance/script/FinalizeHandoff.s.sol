// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {AgentSettlementVault} from "../contracts/AgentSettlementVault.sol";
import {EuroSettlementToken} from "../contracts/EuroSettlementToken.sol";
import {BankRegistry} from "../contracts/BankRegistry.sol";
import {InterbankSettlement} from "../contracts/InterbankSettlement.sol";
import {PIDBudgetController} from "../contracts/PIDBudgetController.sol";
import {ReversibleRandomTimelock} from "../contracts/ReversibleRandomTimelock.sol";

/// @notice Explicit second deployment phase, run only after governance accepts the handoff.
contract FinalizeHandoff is Script {
    error GovernanceNotReady();

    struct Actors {
        address deployer;
        address governance;
        address proposer;
        address canceller;
        address executor;
        address attestor;
        address velocityOracle;
        address bankRegistrar;
        address bankSuspender;
        address liquidityManager;
        address interbankPauser;
    }

    struct Contracts {
        EuroSettlementToken token;
        PIDBudgetController controller;
        AgentSettlementVault vault;
        ReversibleRandomTimelock timelock;
        BankRegistry bankRegistry;
        InterbankSettlement interbankSettlement;
    }

    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        Actors memory actors = _readActors(vm.addr(deployerKey));
        Contracts memory deployed = _readContracts();

        if (!_actorsAreSafe(actors) || !_rolesAreReady(deployed, actors)) {
            revert GovernanceNotReady();
        }

        vm.startBroadcast(deployerKey);
        _renounceBootstrapRoles(deployed, actors.deployer);
        vm.stopBroadcast();
    }

    function _readActors(address deployer) private view returns (Actors memory actors) {
        actors.deployer = deployer;
        actors.governance = vm.envAddress("GOVERNANCE_ADDRESS");
        actors.proposer = vm.envAddress("PROPOSER_ADDRESS");
        actors.canceller = vm.envAddress("CANCELLER_ADDRESS");
        actors.executor = vm.envAddress("EXECUTOR_ADDRESS");
        actors.attestor = vm.envAddress("METERING_ATTESTOR_ADDRESS");
        actors.velocityOracle = vm.envAddress("VELOCITY_ORACLE_ADDRESS");
        actors.bankRegistrar = vm.envAddress("BANK_REGISTRAR_ADDRESS");
        actors.bankSuspender = vm.envAddress("BANK_SUSPENDER_ADDRESS");
        actors.liquidityManager = vm.envAddress("LIQUIDITY_MANAGER_ADDRESS");
        actors.interbankPauser = vm.envAddress("INTERBANK_PAUSER_ADDRESS");
    }

    function _readContracts() private view returns (Contracts memory deployed) {
        deployed.token = EuroSettlementToken(vm.envAddress("TOKEN_ADDRESS"));
        deployed.controller = PIDBudgetController(vm.envAddress("PID_CONTROLLER_ADDRESS"));
        deployed.vault = AgentSettlementVault(vm.envAddress("VAULT_ADDRESS"));
        deployed.timelock = ReversibleRandomTimelock(vm.envAddress("TIMELOCK_ADDRESS"));
        deployed.bankRegistry = BankRegistry(vm.envAddress("BANK_REGISTRY_ADDRESS"));
        deployed.interbankSettlement =
            InterbankSettlement(vm.envAddress("INTERBANK_SETTLEMENT_ADDRESS"));
    }

    function _actorsAreSafe(Actors memory actors) private pure returns (bool) {
        return actors.governance != address(0) && actors.governance != actors.deployer
            && actors.proposer != actors.deployer && actors.canceller != actors.deployer
            && actors.executor != actors.deployer && actors.attestor != actors.deployer
            && actors.velocityOracle != actors.deployer
            && actors.bankRegistrar != address(0) && actors.bankSuspender != address(0)
            && actors.liquidityManager != address(0) && actors.interbankPauser != address(0)
            && actors.bankRegistrar != actors.deployer
            && actors.bankSuspender != actors.deployer
            && actors.liquidityManager != actors.deployer
            && actors.interbankPauser != actors.deployer;
    }

    function _rolesAreReady(Contracts memory deployed, Actors memory actors)
        private
        view
        returns (bool)
    {
        return _coreRolesAreReady(deployed, actors)
            && _interbankRolesAreReady(deployed, actors);
    }

    function _coreRolesAreReady(Contracts memory deployed, Actors memory actors)
        private
        view
        returns (bool)
    {
        return deployed.token.hasRole(deployed.token.DEFAULT_ADMIN_ROLE(), actors.governance)
            && deployed.token.hasRole(deployed.token.ISSUER_ROLE(), actors.governance)
            && deployed.token.hasRole(deployed.token.COMPLIANCE_ROLE(), actors.governance)
            && deployed.token.hasRole(deployed.token.PAUSER_ROLE(), actors.governance)
            && deployed.controller.hasRole(
                deployed.controller.DEFAULT_ADMIN_ROLE(), actors.governance
            )
            && deployed.controller.hasRole(
                deployed.controller.ORACLE_ROLE(), actors.velocityOracle
            )
            && deployed.vault.hasRole(deployed.vault.DEFAULT_ADMIN_ROLE(), actors.governance)
            && deployed.vault.hasRole(deployed.vault.ATTESTOR_ROLE(), actors.attestor)
            && deployed.timelock.hasRole(
                deployed.timelock.DEFAULT_ADMIN_ROLE(), actors.governance
            )
            && deployed.timelock.hasRole(
                deployed.timelock.PROPOSER_ROLE(), actors.proposer
            )
            && deployed.timelock.hasRole(
                deployed.timelock.CANCELLER_ROLE(), actors.canceller
            )
            && deployed.timelock.hasRole(
                deployed.timelock.EXECUTOR_ROLE(), actors.executor
            );
    }

    function _interbankRolesAreReady(Contracts memory deployed, Actors memory actors)
        private
        view
        returns (bool)
    {
        return deployed.bankRegistry.hasRole(
            deployed.bankRegistry.DEFAULT_ADMIN_ROLE(), actors.governance
        )
            && deployed.bankRegistry.hasRole(
                deployed.bankRegistry.REGISTRAR_ROLE(), actors.bankRegistrar
            )
            && deployed.bankRegistry.hasRole(
                deployed.bankRegistry.SUSPENDER_ROLE(), actors.bankSuspender
            )
            && deployed.interbankSettlement.hasRole(
                deployed.interbankSettlement.DEFAULT_ADMIN_ROLE(), actors.governance
            )
            && deployed.interbankSettlement.hasRole(
                deployed.interbankSettlement.LIQUIDITY_MANAGER_ROLE(), actors.liquidityManager
            )
            && deployed.interbankSettlement.hasRole(
                deployed.interbankSettlement.PAUSER_ROLE(), actors.interbankPauser
            );
    }

    function _renounceBootstrapRoles(Contracts memory deployed, address deployer) private {
        deployed.token.renounceRole(deployed.token.ISSUER_ROLE(), deployer);
        deployed.token.renounceRole(deployed.token.COMPLIANCE_ROLE(), deployer);
        deployed.token.renounceRole(deployed.token.PAUSER_ROLE(), deployer);
        deployed.token.renounceRole(deployed.token.DEFAULT_ADMIN_ROLE(), deployer);
        deployed.controller.renounceRole(deployed.controller.DEFAULT_ADMIN_ROLE(), deployer);
        deployed.vault.renounceRole(deployed.vault.ATTESTOR_ROLE(), deployer);
        deployed.vault.renounceRole(deployed.vault.DEFAULT_ADMIN_ROLE(), deployer);
        deployed.timelock.renounceRole(deployed.timelock.PROPOSER_ROLE(), deployer);
        deployed.timelock.renounceRole(deployed.timelock.CANCELLER_ROLE(), deployer);
        deployed.timelock.renounceRole(deployed.timelock.EXECUTOR_ROLE(), deployer);
        deployed.timelock.renounceRole(deployed.timelock.DEFAULT_ADMIN_ROLE(), deployer);
        deployed.bankRegistry.renounceRole(deployed.bankRegistry.REGISTRAR_ROLE(), deployer);
        deployed.bankRegistry.renounceRole(deployed.bankRegistry.SUSPENDER_ROLE(), deployer);
        deployed.bankRegistry.renounceRole(
            deployed.bankRegistry.DEFAULT_ADMIN_ROLE(), deployer
        );
        deployed.interbankSettlement.renounceRole(
            deployed.interbankSettlement.LIQUIDITY_MANAGER_ROLE(), deployer
        );
        deployed.interbankSettlement.renounceRole(
            deployed.interbankSettlement.PAUSER_ROLE(), deployer
        );
        deployed.interbankSettlement.renounceRole(
            deployed.interbankSettlement.DEFAULT_ADMIN_ROLE(), deployer
        );
    }
}
