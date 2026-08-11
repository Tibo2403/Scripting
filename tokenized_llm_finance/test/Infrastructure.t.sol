// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

import {
    AgentSettlementVault,
    IBudgetController
} from "../contracts/AgentSettlementVault.sol";
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
    uint256 private constant ATTESTOR_KEY = 0xA77E57;
    address private constant AGENT = address(0xA11CE);
    address private constant BENEFICIARY = address(0xBEEF);

    EuroSettlementToken private token;
    PIDBudgetController private controller;
    AgentSettlementVault private vault;
    ReversibleRandomTimelock private timelock;
    MockCoordinator private coordinator;

    function setUp() public {
        token = new EuroSettlementToken(address(this));
        controller = new PIDBudgetController(address(this), address(this), 1, 1 hours);
        controller.configureAgent(
            AGENT,
            PIDBudgetController.AgentConfiguration({
                initialBudgetWad: 1_000 * WAD,
                minimumBudgetWad: 100 * WAD,
                maximumBudgetWad: 2_000 * WAD,
                targetVelocityWad: 100 * WAD,
                maximumVelocityWad: 1_000 * WAD,
                maximumBudgetChangeWad: 200 * WAD,
                kpWad: 1 * WAD,
                kiWad: 0,
                kdWad: 0,
                integralMinimumWadSeconds: -10_000 * int256(WAD),
                integralMaximumWadSeconds: 10_000 * int256(WAD)
            })
        );
        vault = new AgentSettlementVault(
            address(this), token, IBudgetController(address(controller)), 1 days, 1 days
        );
        vault.grantRole(vault.ATTESTOR_ROLE(), vm.addr(ATTESTOR_KEY));
        coordinator = new MockCoordinator();
        timelock = new ReversibleRandomTimelock(
            address(this),
            address(coordinator),
            1,
            bytes32(uint256(2)),
            1 hours,
            30 minutes,
            15 minutes,
            3,
            250_000
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
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-1"), 5 * WAD);
        bytes32 digest = vault.hashUsageReceipt(receipt);
        bytes memory data = abi.encodeCall(vault.settle, (receipt, signature));
        (bytes32 operationId, uint256 requestId) = timelock.queue(
            address(vault), data, digest
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
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-2"), 5 * WAD);
        bytes memory data = abi.encodeCall(vault.settle, (receipt, signature));
        (bytes32 operationId,) =
            timelock.queue(address(vault), data, vault.hashUsageReceipt(receipt));
        timelock.cancel(operationId);

        ReversibleRandomTimelock.Operation memory operation = timelock.getOperation(operationId);
        assertEq(uint8(operation.status), uint8(ReversibleRandomTimelock.Status.Cancelled));
    }

    function testCancelledSemanticKeyCannotBeQueuedAgain() public {
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-no-grinding"), 5 * WAD);
        bytes32 semanticKey = vault.hashUsageReceipt(receipt);
        bytes memory data = abi.encodeCall(vault.settle, (receipt, signature));
        (bytes32 operationId,) = timelock.queue(address(vault), data, semanticKey);
        timelock.cancel(operationId);

        vm.expectRevert(
            abi.encodeWithSelector(
                ReversibleRandomTimelock.SemanticKeyAlreadyUsed.selector, semanticKey
            )
        );
        timelock.queue(address(vault), data, semanticKey);
    }

    function testTargetRevocationInvalidatesAlreadyQueuedOperation() public {
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-revoked"), 5 * WAD);
        bytes memory data = abi.encodeCall(vault.settle, (receipt, signature));
        (bytes32 operationId, uint256 requestId) =
            timelock.queue(address(vault), data, vault.hashUsageReceipt(receipt));
        coordinator.fulfill(address(timelock), requestId, 0);
        timelock.setTargetAllowed(address(vault), false);
        timelock.setTargetAllowed(address(vault), true);
        ReversibleRandomTimelock.Operation memory operation = timelock.getOperation(operationId);
        vm.warp(operation.readyAt);
        vm.expectRevert(
            abi.encodeWithSelector(
                ReversibleRandomTimelock.TargetPermissionChangedSinceQueue.selector,
                address(vault)
            )
        );
        timelock.execute(operationId);
    }

    function testScheduledOperationExpires() public {
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-expired"), 5 * WAD);
        bytes memory data = abi.encodeCall(vault.settle, (receipt, signature));
        (bytes32 operationId, uint256 requestId) =
            timelock.queue(address(vault), data, vault.hashUsageReceipt(receipt));
        coordinator.fulfill(address(timelock), requestId, 0);
        ReversibleRandomTimelock.Operation memory operation = timelock.getOperation(operationId);
        vm.warp(operation.executeBefore + 1);
        vm.expectRevert(
            abi.encodeWithSelector(
                ReversibleRandomTimelock.OperationExpired.selector, operation.executeBefore
            )
        );
        timelock.execute(operationId);
    }

    function testForgedMeteringSignatureIsRejected() public {
        (AgentSettlementVault.UsageReceipt memory receipt,) =
            _signedReceipt(keccak256("usage-forged"), 5 * WAD);
        bytes32 digest = vault.hashUsageReceipt(receipt);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(0xBAD, digest);
        bytes memory forgedSignature = abi.encodePacked(r, s, v);
        vm.expectRevert();
        vm.prank(address(timelock));
        vault.settle(receipt, forgedSignature);
    }

    function testSignedAmountCannotBeAltered() public {
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-altered"), 5 * WAD);
        receipt.amountWad = 50 * WAD;

        vm.expectRevert();
        vm.prank(address(timelock));
        vault.settle(receipt, signature);
    }

    function testSignedReceiptCannotBeReplayed() public {
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-replay"), 5 * WAD);
        bytes32 digest = vault.hashUsageReceipt(receipt);

        vm.startPrank(address(timelock));
        vault.settle(receipt, signature);
        vm.expectRevert(
            abi.encodeWithSelector(AgentSettlementVault.DuplicateUsage.selector, digest)
        );
        vault.settle(receipt, signature);
        vm.stopPrank();
    }

    function testExpiredSignedReceiptIsRejected() public {
        (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature) =
            _signedReceipt(keccak256("usage-stale"), 5 * WAD);
        vm.warp(receipt.deadline + 1);

        vm.expectRevert(AgentSettlementVault.InvalidUsageTime.selector);
        vm.prank(address(timelock));
        vault.settle(receipt, signature);
    }

    function _signedReceipt(bytes32 providerRequestId, uint256 amountWad)
        private
        view
        returns (AgentSettlementVault.UsageReceipt memory receipt, bytes memory signature)
    {
        receipt = AgentSettlementVault.UsageReceipt({
            agent: AGENT,
            beneficiary: BENEFICIARY,
            providerRequestId: providerRequestId,
            modelId: keccak256("model"),
            tariffId: keccak256("tariff-v1"),
            responseHash: keccak256("response"),
            promptTokens: 100,
            completionTokens: 20,
            energyKwhWad: 1e15,
            amountWad: amountWad,
            usageTimestamp: block.timestamp,
            usageEpoch: block.timestamp / vault.epochDuration(),
            nonce: uint256(providerRequestId),
            deadline: block.timestamp + 8 hours
        });
        bytes32 digest = vault.hashUsageReceipt(receipt);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(ATTESTOR_KEY, digest);
        signature = abi.encodePacked(r, s, v);
    }
}
