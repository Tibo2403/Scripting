// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

library VRFV2PlusClientLite {
    // Same tagged encoding used by Chainlink VRF v2.5 ExtraArgsV1.
    bytes4 internal constant EXTRA_ARGS_V1_TAG = bytes4(keccak256("VRF ExtraArgsV1"));

    struct ExtraArgsV1 { bool nativePayment; }
    struct RandomWordsRequest {
        bytes32 keyHash;
        uint256 subId;
        uint16 requestConfirmations;
        uint32 callbackGasLimit;
        uint32 numWords;
        bytes extraArgs;
    }

    function args(bool nativePayment) internal pure returns (bytes memory) {
        return abi.encodeWithSelector(EXTRA_ARGS_V1_TAG, ExtraArgsV1({nativePayment: nativePayment}));
    }
}

interface IVRFCoordinatorV2PlusLite {
    function requestRandomWords(VRFV2PlusClientLite.RandomWordsRequest calldata request)
        external returns (uint256 requestId);
}

/// @notice VRF-randomized, asynchronous timelock whose queued calls remain cancellable until execution.
contract ReversibleRandomTimelock is AccessControl, ReentrancyGuard {
    bytes32 public constant PROPOSER_ROLE = keccak256("PROPOSER_ROLE");
    bytes32 public constant CANCELLER_ROLE = keccak256("CANCELLER_ROLE");
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");

    enum Status { None, AwaitingRandomness, Scheduled, Cancelled, Executed }
    struct Operation {
        address target;
        uint64 readyAt;
        Status status;
        bytes data;
    }

    IVRFCoordinatorV2PlusLite public immutable coordinator;
    uint256 public immutable subscriptionId;
    bytes32 public immutable keyHash;
    uint64 public immutable minimumDelay;
    uint64 public immutable noiseWindow;
    uint16 public immutable requestConfirmations;
    uint32 public immutable callbackGasLimit;

    mapping(bytes32 operationId => Operation operation) private _operations;
    mapping(uint256 requestId => bytes32 operationId) public requestToOperation;
    mapping(address target => bool allowed) public allowedTarget;

    error InvalidConfiguration();
    error TargetNotAllowed(address target);
    error InvalidStatus(Status expected, Status actual);
    error RandomnessOnlyCoordinator();
    error NotReady(uint64 readyAt);
    error UnderlyingCallFailed(bytes returnData);

    event TargetPermissionChanged(address indexed target, bool allowed);
    event OperationQueued(bytes32 indexed operationId, uint256 indexed requestId, address indexed target);
    event OperationScheduled(bytes32 indexed operationId, uint64 readyAt, uint64 randomDelay);
    event OperationCancelled(bytes32 indexed operationId);
    event OperationExecuted(bytes32 indexed operationId, bytes returnData);

    constructor(
        address admin,
        address vrfCoordinator,
        uint256 vrfSubscriptionId,
        bytes32 vrfKeyHash,
        uint64 minimumDelaySeconds,
        uint64 noiseWindowSeconds,
        uint16 confirmations,
        uint32 vrfCallbackGasLimit
    ) {
        if (
            admin == address(0) || vrfCoordinator == address(0) || minimumDelaySeconds == 0 ||
            minimumDelaySeconds > type(uint64).max - noiseWindowSeconds ||
            confirmations == 0 || vrfCallbackGasLimit == 0
        ) revert InvalidConfiguration();
        coordinator = IVRFCoordinatorV2PlusLite(vrfCoordinator);
        subscriptionId = vrfSubscriptionId;
        keyHash = vrfKeyHash;
        minimumDelay = minimumDelaySeconds;
        noiseWindow = noiseWindowSeconds;
        requestConfirmations = confirmations;
        callbackGasLimit = vrfCallbackGasLimit;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PROPOSER_ROLE, admin);
        _grantRole(CANCELLER_ROLE, admin);
        _grantRole(EXECUTOR_ROLE, admin);
    }

    function setTargetAllowed(address target, bool allowed) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (target == address(0)) revert InvalidConfiguration();
        allowedTarget[target] = allowed;
        emit TargetPermissionChanged(target, allowed);
    }

    function queue(address target, bytes calldata data, bytes32 salt)
        external onlyRole(PROPOSER_ROLE) returns (bytes32 operationId, uint256 requestId)
    {
        if (!allowedTarget[target]) revert TargetNotAllowed(target);
        operationId = keccak256(abi.encode(block.chainid, address(this), target, data, salt));
        Status current = _operations[operationId].status;
        if (current != Status.None) revert InvalidStatus(Status.None, current);

        _operations[operationId] = Operation({
            target: target,
            readyAt: 0,
            status: Status.AwaitingRandomness,
            data: data
        });
        requestId = coordinator.requestRandomWords(VRFV2PlusClientLite.RandomWordsRequest({
            keyHash: keyHash,
            subId: subscriptionId,
            requestConfirmations: requestConfirmations,
            callbackGasLimit: callbackGasLimit,
            numWords: 1,
            extraArgs: VRFV2PlusClientLite.args(false)
        }));
        requestToOperation[requestId] = operationId;
        emit OperationQueued(operationId, requestId, target);
    }

    /// @notice Chainlink-compatible callback entry point; cancelled requests are safely ignored.
    function rawFulfillRandomWords(uint256 requestId, uint256[] calldata randomWords) external {
        if (msg.sender != address(coordinator)) revert RandomnessOnlyCoordinator();
        bytes32 operationId = requestToOperation[requestId];
        Operation storage operation = _operations[operationId];
        if (operation.status == Status.Cancelled) return;
        if (operation.status != Status.AwaitingRandomness) {
            revert InvalidStatus(Status.AwaitingRandomness, operation.status);
        }
        uint64 jitter = uint64(randomWords[0] % (uint256(noiseWindow) + 1));
        uint64 delay = minimumDelay + jitter;
        operation.readyAt = uint64(block.timestamp) + delay;
        operation.status = Status.Scheduled;
        emit OperationScheduled(operationId, operation.readyAt, delay);
    }

    function cancel(bytes32 operationId) external onlyRole(CANCELLER_ROLE) {
        Operation storage operation = _operations[operationId];
        if (operation.status != Status.AwaitingRandomness && operation.status != Status.Scheduled) {
            revert InvalidStatus(Status.Scheduled, operation.status);
        }
        operation.status = Status.Cancelled;
        emit OperationCancelled(operationId);
    }

    function execute(bytes32 operationId)
        external onlyRole(EXECUTOR_ROLE) nonReentrant returns (bytes memory returnData)
    {
        Operation storage operation = _operations[operationId];
        if (operation.status != Status.Scheduled) revert InvalidStatus(Status.Scheduled, operation.status);
        if (block.timestamp < operation.readyAt) revert NotReady(operation.readyAt);

        operation.status = Status.Executed;
        (bool success, bytes memory result) = operation.target.call(operation.data);
        if (!success) revert UnderlyingCallFailed(result);
        emit OperationExecuted(operationId, result);
        return result;
    }

    function getOperation(bytes32 operationId) external view returns (Operation memory) {
        return _operations[operationId];
    }
}
