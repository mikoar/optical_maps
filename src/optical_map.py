from __future__ import annotations
from scipy.signal import find_peaks
from typing import List
import numpy as np
from scipy.signal import correlate
from alignment import Alignment
from peak import Peak

from validator import Validator


class OpticalMap:
    def __init__(self, moleculeId: int, sequence: np.ndarray, positions:  List[int], resolution: int) -> None:
        self.sequence = sequence
        self.positions = positions
        self.moleculeId = moleculeId
        self.resolution = resolution

    def correlate(self, reference: np.ndarray, reverseStrand=False, flatten=True):
        if reverseStrand:
            self.sequence = self.sequence[::-1]

        correlation = self.__getCorrelation(reference, self.sequence)

        if flatten:
            normalizingFactor = self.__getCorrelation(reference, np.ones(len(self.sequence))) + np.sum(self.sequence)
            correlation = correlation / normalizingFactor

        correlation /= np.max(correlation)

        return CorrelationResult(correlation, self, reference)

    def __getCorrelation(self, reference: np.ndarray, query: np.ndarray) -> np.ndarray:
        return correlate(reference, query, mode='same', method='fft')


class CorrelationResult:
    def __init__(self, correlation: np.ndarray, query: OpticalMap, reference: np.ndarray) -> None:
        self.correlation = correlation
        self.query = query
        self.reference = reference


class Peaks:
    def __init__(self, correlationResult: CorrelationResult) -> None:
        self.correlationResult = correlationResult
        self.peakPositions, self.peakProperties = find_peaks(correlationResult.correlation,
                                                             height=0.01,
                                                             prominence=0.2,
                                                             distance=((5 * 10 ** 6) / correlationResult.query.resolution))

    def getRelativeScore(self, reference: Alignment, validator: Validator):
        maxPeak = self.max
        isMaxValid = validator.validate(maxPeak, reference)
        if maxPeak and isMaxValid:
            peakHeight = maxPeak.height
        else:
            peakHeight = self.__getMaxValidPeakHeight(reference, validator) or self.__getMaxCorrelationValueInAlignmentRange(reference)
        return self.__score(peakHeight)

    @property
    def max(self):
        if not self.peakPositions.any():
            return

        maxIndex = np.argmax(self.__peakHeights)
        return Peak(self.peakPositions[maxIndex] * self.correlationResult.query.resolution, self.__peakHeights[maxIndex])

    @property
    def __peaks(self):
        for position, height in zip(self.peakPositions, self.__peakHeights):
            yield Peak(position * self.correlationResult.query.resolution, height)

    @property
    def __peakHeights(self) -> List[float]:
        return self.peakProperties["peak_heights"]

    def __getMaxValidPeakHeight(self, reference: Alignment, validator: Validator):
        validPeaks = [peak for peak in self.__peaks if validator.validate(peak, reference)]
        maxValidPeakHeight = max(validPeaks, key=lambda peak: peak.height).height if validPeaks else None
        return maxValidPeakHeight

    def __getMaxCorrelationValueInAlignmentRange(self, reference: Alignment) -> float:
        expectedQueryStartPosition = reference.expectedQueryStart / self.correlationResult.query.resolution
        expectedQueryEndPosition = reference.expectedQueryStart / self.correlationResult.query.resolution
        return np.max(self.correlationResult.correlation[expectedQueryStartPosition: expectedQueryEndPosition])

    def __score(self, peakHeight: float | None):
        order = 5
        heights = self.__peakHeights

        if len(heights) < order:
            return 1.

        firstPeakHeight, nthPeakHeight = sorted(heights, reverse=True)[:order:order - 1]
        peakHeightToScore = peakHeight if peakHeight else firstPeakHeight
        return peakHeightToScore - nthPeakHeight
