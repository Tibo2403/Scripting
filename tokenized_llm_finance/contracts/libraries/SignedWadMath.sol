// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";

/// @notice Signed fixed-point helpers using 18 decimals and full-precision Math.mulDiv.
library SignedWadMath {
    uint256 internal constant WAD = 1e18;

    error SignedOverflow();

    function mulWad(int256 value, uint256 coefficientWad) internal pure returns (int256) {
        bool negative = value < 0;
        uint256 magnitude = negative ? uint256(-(value + 1)) + 1 : uint256(value);
        uint256 result = Math.mulDiv(magnitude, coefficientWad, WAD);

        if (negative) {
            if (result > uint256(1) << 255) revert SignedOverflow();
            if (result == uint256(1) << 255) return type(int256).min;
            return -int256(result);
        }
        if (result > uint256(type(int256).max)) revert SignedOverflow();
        return int256(result);
    }

    function clamp(int256 value, int256 minimum, int256 maximum) internal pure returns (int256) {
        if (value < minimum) return minimum;
        if (value > maximum) return maximum;
        return value;
    }
}
