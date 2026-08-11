// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

import {AgentSettlementVault} from "../contracts/AgentSettlementVault.sol";
import {EuroSettlementToken} from "../contracts/EuroSettlementToken.sol";
import {PIDBudgetController} from "../contracts/PIDBudgetController.sol";
import {
    IVRFCoordinatorV2PlusLite,
    ReversibleRandomTimelock,
    VRFV2PlusClientLite
} from "../contracts/ReversibleRandomTimelock.sol";

contract MockCoordinator is IVRFCoordinatorV2PlusLite {
    uint256 public nextRequestId = 1;

    function requestRandomWords(VRFV2PlusClientLite.RandomWordsRequest calldata)
        external returns (uint256 requestId)
    {
        requestId = nextRequestId++;
    }

    function fulfill(address consumer, uint256 requestId, uint256 word) external {
        uint256[] memory words = new uint256[](1);
        words[0] = word;
        ReversibleRandomTimelock(consumer).rawFulfillRandomWords(requestId, words);
    }
}

contract InfrastructureTest is Test {
    uint256 private constant WAD = 1e18;
    address private constant AGENT = address(0xA11CE);
    address private constant BENEFICIARY = address(0xBEEF);

    EuroSettlementToken private token;
    PIDBudgetController private controller;
    AgentSettlementVault private vault;
    ReversibleRandomTimelock private timelock;
    MockCoordinator private coordinator;

    function setUp() public {
        token = new EuroSettlementToken(address(this));
        controller = new PIDBudgetController(address(this), address(this));
        controller.configureAgent(
            AGENT,
            1_000 * WAD,
            100 * WAD,
            2_000 * WAD,
            100 * WAD,
            1 * WAD,
            0,
            0,
            -10_000 * int256(WAD),
            10_000 * int256(WAD)
        );
        vault = new AgentSettlementVault(address(this), token, controller, 1 days);
        coordinator = new MockCoordinator();
        timelock = new ReversibleRandomTimelock(
            address(this), address(coordinator), 1, bytes32(uint256(2)), 1 hours, 30 minutes, 3, 250_000
        );

        token.setAllowed(address(vault), true);
        token.setAllowed(BENEFICIARY, true);
        token.mint(address(vault), 10_000 * WAD);
        vault.grantRole(vault.SETTLER_ROLE(), address(timelock));
        timelock.setTargetAllowed(address(vault), true);
    }

    function testPidReducesBudgetWhenVelocityExceedsTarget() public {
        vm.warp(block.timestamp + 10);
        uint256 newBudget = controller.updateBudget(AGENT, 200 * WAD);
        assertEq(newBudget, 900 * WAD);
    }

    function testVrfDelayThenSettlement() public {
        bytes32 digest = keccak256("usage-1");
        bytes memory data = abi.encodeCall(
            vault.settle, (AGENT, BENEFICIARY, 5 * WAD, digest)
        );
        (bytes32 operationId, uint256 requestId) = timelock.queue(
            address(vault), data, keccak256("salt-1")
        );

        coordinator.fulfill(address(timelock), requestId, 7);
        ReversibleRandomTimelock.Operation memory operation = timelock.getOperation(operationId);
        assertEq(uint8(operation.status), uint8(ReversibleRandomTimelock.Status.Scheduled));
        assertEq(operation.readyAt, block.timestamp + 1 hours + 7);

        vm.warp(operation.readyAt);
        timelock.execute(operationId);
        assertEq(token.balanceOf(BENEFICIARY), 5 * WAD);
        assertTrue(vault.settledUsage(digest));
    }

    function testSupervisorCanCancelBeforeRandomness() public {
        bytes memory data = abi.encodeCall(
            vault.settle, (AGENT, BENEFICIARY, 5 * WAD, keccak256("usage-2"))
        );
        (bytes32 operationId,) = timelock.queue(address(vault), data, keccak256("salt-2"));
        timelock.cancel(operationId);

        ReversibleRandomTimelock.Operation memory operation = timelock.getOperation(operationId);
        assertEq(uint8(operation.status), uint8(ReversibleRandomTimelock.Status.Cancelled));
    }
}
