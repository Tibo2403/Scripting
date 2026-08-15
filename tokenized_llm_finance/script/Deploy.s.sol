// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";

import {
    AgentSettlementVault,
    IBudgetController
} from "../contracts/AgentSettlementVault.sol";
import {EuroSettlementToken} from "../contracts/EuroSettlementToken.sol";
import {BankRegistry} from "../contracts/BankRegistry.sol";
import {InterbankSettlement} from "../contracts/InterbankSettlement.sol";
import {PIDBudgetController} from "../contracts/PIDBudgetController.sol";
import {ReversibleRandomTimelock} from "../contracts/ReversibleRandomTimelock.sol";

contract Deploy is Script {
    error InvalidDeploymentConfiguration();
    error IntegerDoesNotFit();

    struct DeploymentConfig {
        uint256 deployerKey;
        address deployer;
        address governance;
        address proposer;
        address canceller;
        address executor;
        address attestor;
        address velocityOracle;
        address coordinator;
        address bankRegistrar;
        address bankSuspender;
        address liquidityManager;
        address interbankPauser;
        uint256 subscriptionId;
        bytes32 keyHash;
    }

    function run()
        external
        returns (
            EuroSettlementToken token,
            PIDBudgetController controller,
            AgentSettlementVault vault,
            ReversibleRandomTimelock timelock,
            BankRegistry bankRegistry,
            InterbankSettlement interbankSettlement
        )
    {
        DeploymentConfig memory config = _readConfiguration();

        vm.startBroadcast(config.deployerKey);
        token = new EuroSettlementToken(config.deployer);
        controller = new PIDBudgetController(
            config.deployer,
            config.velocityOracle,
            _asUint64(vm.envUint("PID_MIN_UPDATE_SECONDS")),
            _asUint64(vm.envUint("PID_MAX_ELAPSED_SECONDS"))
        );
        vault = new AgentSettlementVault(
            config.deployer,
            token,
            IBudgetController(address(controller)),
            _asUint64(vm.envUint("BUDGET_EPOCH_SECONDS")),
            _asUint64(vm.envUint("MAXIMUM_USAGE_AGE_SECONDS"))
        );
        timelock = new ReversibleRandomTimelock(
            config.deployer,
            config.coordinator,
            config.subscriptionId,
            config.keyHash,
            _asUint64(vm.envUint("MINIMUM_DELAY_SECONDS")),
            _asUint64(vm.envUint("NOISE_WINDOW_SECONDS")),
            _asUint64(vm.envUint("EXECUTION_WINDOW_SECONDS")),
            _asUint16(vm.envUint("VRF_CONFIRMATIONS")),
            _asUint32(vm.envUint("VRF_CALLBACK_GAS_LIMIT"))
        );
        bankRegistry = new BankRegistry(config.deployer);
        interbankSettlement = new InterbankSettlement(
            config.deployer,
            token,
            bankRegistry,
            _asUint64(vm.envUint("INTERBANK_EPOCH_SECONDS")),
            _asUint64(vm.envUint("MAX_INTERBANK_INSTRUCTION_LIFETIME_SECONDS"))
        );

        _wireContracts(
            token,
            controller,
            vault,
            timelock,
            bankRegistry,
            interbankSettlement,
            config
        );
        vm.stopBroadcast();

        // Run FinalizeHandoff only after governance verifies every deployed address and role.
    }

    function _readConfiguration() private view returns (DeploymentConfig memory config) {
        config.deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        config.deployer = vm.addr(config.deployerKey);
        config.governance = vm.envAddress("GOVERNANCE_ADDRESS");
        config.proposer = vm.envAddress("PROPOSER_ADDRESS");
        config.canceller = vm.envAddress("CANCELLER_ADDRESS");
        config.executor = vm.envAddress("EXECUTOR_ADDRESS");
        config.attestor = vm.envAddress("METERING_ATTESTOR_ADDRESS");
        config.velocityOracle = vm.envAddress("VELOCITY_ORACLE_ADDRESS");
        config.coordinator = vm.envAddress("VRF_COORDINATOR_ADDRESS");
        config.bankRegistrar = vm.envAddress("BANK_REGISTRAR_ADDRESS");
        config.bankSuspender = vm.envAddress("BANK_SUSPENDER_ADDRESS");
        config.liquidityManager = vm.envAddress("LIQUIDITY_MANAGER_ADDRESS");
        config.interbankPauser = vm.envAddress("INTERBANK_PAUSER_ADDRESS");
        if (
            config.deployerKey == 0 || config.governance == address(0) ||
            config.proposer == address(0) || config.canceller == address(0) ||
            config.executor == address(0) || config.attestor == address(0) ||
            config.velocityOracle == address(0) || config.coordinator == address(0) ||
            config.bankRegistrar == address(0) || config.bankSuspender == address(0) ||
            config.liquidityManager == address(0) || config.interbankPauser == address(0) ||
            config.governance == config.deployer || config.proposer == config.deployer ||
            config.canceller == config.deployer || config.executor == config.deployer ||
            config.attestor == config.deployer || config.velocityOracle == config.deployer ||
            config.proposer == config.canceller || config.proposer == config.executor ||
            config.canceller == config.executor || config.proposer == config.attestor ||
            config.canceller == config.attestor || config.executor == config.attestor ||
            config.proposer == config.velocityOracle ||
            config.canceller == config.velocityOracle ||
            config.executor == config.velocityOracle || config.attestor == config.velocityOracle
        ) revert InvalidDeploymentConfiguration();
        if (
            config.bankRegistrar == config.deployer ||
            config.bankSuspender == config.deployer ||
            config.liquidityManager == config.deployer ||
            config.interbankPauser == config.deployer
        ) revert InvalidDeploymentConfiguration();

        config.subscriptionId = vm.envUint("VRF_SUBSCRIPTION_ID");
        config.keyHash = vm.envBytes32("VRF_KEY_HASH");
        if (config.subscriptionId == 0 || config.keyHash == bytes32(0)) {
            revert InvalidDeploymentConfiguration();
        }
    }

    function _wireContracts(
        EuroSettlementToken token,
        PIDBudgetController controller,
        AgentSettlementVault vault,
        ReversibleRandomTimelock timelock,
        BankRegistry bankRegistry,
        InterbankSettlement interbankSettlement,
        DeploymentConfig memory config
    ) private {
        token.setAllowed(address(vault), true);
        vault.grantRole(vault.SETTLER_ROLE(), address(timelock));
        vault.grantRole(vault.ATTESTOR_ROLE(), config.attestor);
        timelock.setTargetAllowed(address(vault), true);

        token.grantRole(token.DEFAULT_ADMIN_ROLE(), config.governance);
        token.grantRole(token.ISSUER_ROLE(), config.governance);
        token.grantRole(token.COMPLIANCE_ROLE(), config.governance);
        token.grantRole(token.PAUSER_ROLE(), config.governance);
        controller.grantRole(controller.DEFAULT_ADMIN_ROLE(), config.governance);
        vault.grantRole(vault.DEFAULT_ADMIN_ROLE(), config.governance);
        timelock.grantRole(timelock.DEFAULT_ADMIN_ROLE(), config.governance);
        timelock.grantRole(timelock.PROPOSER_ROLE(), config.proposer);
        timelock.grantRole(timelock.CANCELLER_ROLE(), config.canceller);
        timelock.grantRole(timelock.EXECUTOR_ROLE(), config.executor);
        bankRegistry.grantRole(bankRegistry.DEFAULT_ADMIN_ROLE(), config.governance);
        bankRegistry.grantRole(bankRegistry.REGISTRAR_ROLE(), config.bankRegistrar);
        bankRegistry.grantRole(bankRegistry.SUSPENDER_ROLE(), config.bankSuspender);
        interbankSettlement.grantRole(
            interbankSettlement.DEFAULT_ADMIN_ROLE(), config.governance
        );
        interbankSettlement.grantRole(
            interbankSettlement.LIQUIDITY_MANAGER_ROLE(), config.liquidityManager
        );
        interbankSettlement.grantRole(
            interbankSettlement.PAUSER_ROLE(), config.interbankPauser
        );
    }

    function _asUint64(uint256 value) private pure returns (uint64) {
        if (value > type(uint64).max) revert IntegerDoesNotFit();
        return uint64(value);
    }

    function _asUint32(uint256 value) private pure returns (uint32) {
        if (value > type(uint32).max) revert IntegerDoesNotFit();
        return uint32(value);
    }

    function _asUint16(uint256 value) private pure returns (uint16) {
        if (value > type(uint16).max) revert IntegerDoesNotFit();
        return uint16(value);
    }
}
