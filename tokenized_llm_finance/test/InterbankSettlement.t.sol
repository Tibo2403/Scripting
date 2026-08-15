// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

import {BankRegistry} from "../contracts/BankRegistry.sol";
import {EuroSettlementToken} from "../contracts/EuroSettlementToken.sol";
import {InterbankSettlement} from "../contracts/InterbankSettlement.sol";

contract InterbankSettlementTest is Test {
    bytes32 private constant BANK_A_ID = keccak256("BANK_A");
    bytes32 private constant BANK_B_ID = keccak256("BANK_B");
    bytes32 private constant BANK_A_BIC_HASH = keccak256("BANKAFRPPXXX");
    bytes32 private constant BANK_B_BIC_HASH = keccak256("BANKBDEFFXXX");
    bytes32 private constant REFERENCE_HASH = keccak256("ISO20022-PACS008-REFERENCE");

    address private bankA = address(0xA11CE);
    address private bankB = address(0xB0B);
    address private outsider = address(0xBAD);

    EuroSettlementToken private token;
    BankRegistry private registry;
    InterbankSettlement private settlement;

    function setUp() public {
        token = new EuroSettlementToken(address(this));
        registry = new BankRegistry(address(this));
        settlement = new InterbankSettlement(
            address(this),
            token,
            registry,
            1 days,
            7 days
        );

        registry.registerBank(BANK_A_ID, BANK_A_BIC_HASH, bankA);
        registry.registerBank(BANK_B_ID, BANK_B_BIC_HASH, bankB);
        settlement.setOutgoingLimit(BANK_A_ID, 1_000 ether);

        token.setAllowed(bankA, true);
        token.setAllowed(bankB, true);
        token.mint(bankA, 2_000 ether);
        vm.prank(bankA);
        token.approve(address(settlement), type(uint256).max);
    }

    function testCreditorAcceptanceSettlesAndTracksLiquidity() public {
        bytes32 instructionId = _initiate(600 ether);

        vm.prank(bankB);
        settlement.acceptAndSettle(instructionId);

        InterbankSettlement.Instruction memory instruction =
            settlement.getInstruction(instructionId);
        assertEq(uint256(instruction.status), uint256(InterbankSettlement.Status.Settled));
        assertEq(token.balanceOf(bankA), 1_400 ether);
        assertEq(token.balanceOf(bankB), 600 ether);
        assertEq(settlement.remainingOutgoingLimit(BANK_A_ID), 400 ether);
    }

    function testOnlyCreditorCanAccept() public {
        bytes32 instructionId = _initiate(100 ether);

        vm.expectRevert(
            abi.encodeWithSelector(
                InterbankSettlement.UnauthorizedBankAccount.selector,
                outsider
            )
        );
        vm.prank(outsider);
        settlement.acceptAndSettle(instructionId);
    }

    function testUnregisteredAccountCannotInitiate() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                InterbankSettlement.UnauthorizedBankAccount.selector,
                outsider
            )
        );
        vm.prank(outsider);
        settlement.initiate(
            keccak256("unauthorized"),
            BANK_B_ID,
            100 ether,
            REFERENCE_HASH,
            uint64(block.timestamp + 1 hours)
        );
    }

    function testSuspendedBankCannotSettle() public {
        bytes32 instructionId = _initiate(100 ether);
        registry.setBankActive(BANK_B_ID, false);

        vm.expectRevert(
            abi.encodeWithSelector(BankRegistry.BankSuspended.selector, BANK_B_ID)
        );
        vm.prank(bankB);
        settlement.acceptAndSettle(instructionId);
    }

    function testOutgoingLiquidityLimitIsEnforced() public {
        bytes32 firstId = _initiateWithId(keccak256("first"), 600 ether);
        vm.prank(bankB);
        settlement.acceptAndSettle(firstId);

        bytes32 secondId = _initiateWithId(keccak256("second"), 500 ether);
        vm.expectRevert(
            abi.encodeWithSelector(
                InterbankSettlement.LiquidityLimitExceeded.selector,
                BANK_A_ID,
                1_000 ether,
                1_100 ether
            )
        );
        vm.prank(bankB);
        settlement.acceptAndSettle(secondId);
    }

    function testExpiredInstructionCannotSettleAndCanBeClosed() public {
        bytes32 instructionId = _initiate(100 ether);
        vm.warp(block.timestamp + 1 hours);

        vm.expectRevert(
            abi.encodeWithSelector(
                InterbankSettlement.InstructionPastExpiry.selector,
                instructionId
            )
        );
        vm.prank(bankB);
        settlement.acceptAndSettle(instructionId);

        settlement.expire(instructionId);
        InterbankSettlement.Instruction memory instruction =
            settlement.getInstruction(instructionId);
        assertEq(uint256(instruction.status), uint256(InterbankSettlement.Status.Expired));
    }

    function testDebtorCanCancelAndInstructionIdCannotBeReused() public {
        bytes32 instructionId = _initiate(100 ether);
        vm.prank(bankA);
        settlement.cancel(instructionId);

        vm.expectRevert(
            abi.encodeWithSelector(
                InterbankSettlement.InstructionAlreadyExists.selector,
                instructionId
            )
        );
        vm.prank(bankA);
        settlement.initiate(
            instructionId,
            BANK_B_ID,
            100 ether,
            REFERENCE_HASH,
            uint64(block.timestamp + 1 hours)
        );
    }

    function testAccountRotationInvalidatesPendingInstruction() public {
        bytes32 instructionId = _initiate(100 ether);
        address newBankB = address(0xBEEF);
        registry.changeSettlementAccount(BANK_B_ID, newBankB);

        vm.expectRevert(
            abi.encodeWithSelector(
                InterbankSettlement.ParticipantAccountChanged.selector,
                BANK_B_ID
            )
        );
        vm.prank(bankB);
        settlement.acceptAndSettle(instructionId);
    }

    function testSettlementPauseBlocksNewInstructions() public {
        settlement.pause();
        vm.expectRevert();
        vm.prank(bankA);
        settlement.initiate(
            keccak256("paused"),
            BANK_B_ID,
            100 ether,
            REFERENCE_HASH,
            uint64(block.timestamp + 1 hours)
        );
    }

    function _initiate(uint256 amountWad) private returns (bytes32 instructionId) {
        instructionId = keccak256(abi.encode("instruction", amountWad, block.timestamp));
        return _initiateWithId(instructionId, amountWad);
    }

    function _initiateWithId(
        bytes32 instructionId,
        uint256 amountWad
    ) private returns (bytes32) {
        vm.prank(bankA);
        settlement.initiate(
            instructionId,
            BANK_B_ID,
            amountWad,
            REFERENCE_HASH,
            uint64(block.timestamp + 1 hours)
        );
        return instructionId;
    }
}

contract BankRegistryTest is Test {
    BankRegistry private registry;

    function setUp() public {
        registry = new BankRegistry(address(this));
    }

    function testSettlementAccountCannotBeSharedByTwoBanks() public {
        address sharedAccount = address(0x1234);
        registry.registerBank(keccak256("A"), keccak256("BIC_A"), sharedAccount);

        vm.expectRevert(
            abi.encodeWithSelector(
                BankRegistry.SettlementAccountAlreadyUsed.selector,
                sharedAccount
            )
        );
        registry.registerBank(keccak256("B"), keccak256("BIC_B"), sharedAccount);
    }
}
