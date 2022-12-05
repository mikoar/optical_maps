from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from math import ceil
from typing import List

import numpy as np
from matplotlib import pyplot
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from src.alignment.alignment_results import AlignmentResultRow
from src.alignment.segments import AlignmentSegment
from src.correlation.optical_map import OpticalMap, PositionWithSiteId, InitialAlignment
from src.correlation.peak import Peak


@dataclass
class Options:
    limitQueryToAlignedArea = False


class AlignmentPlot:
    def __init__(self, reference: OpticalMap, query: OpticalMap, alignment: AlignmentResultRow,
                 correlation: InitialAlignment, options: Options = None):
        self.options = options or Options()
        self.figure: Figure = pyplot.figure(figsize=(24, 16))
        self.axes: Axes = self.figure.add_axes([0, 0, 1, 1])
        self.__setDimensions(alignment, query, correlation)
        self.__plotReference(alignment, reference)
        self.__plotQuery(alignment, query)
        self.__drawPrimaryPeak(correlation)
        self.__plotSegments(alignment)
        self.axes.legend()

    def __setDimensions(self, alignment: AlignmentResultRow, query: OpticalMap, correlation: InitialAlignment):
        offset = alignment.queryLength / 10
        self.yMin = (alignment.queryStartPosition if self.options.limitQueryToAlignedArea else 0) - offset
        drawPeakPositionsWithOffset = list(
            map(lambda s: s.peak.leftProminenceBasePosition - offset, alignment.segments)) + [
                                          correlation.maxPeak.leftProminenceBasePosition - offset]
        self.xMin = min([alignment.referenceStartPosition - offset] + drawPeakPositionsWithOffset)
        self.xMax = alignment.referenceEndPosition
        self.xMinWithOffset = self.xMin - offset
        self.xMaxWithOffset = self.xMax + offset
        self.axes.set_xlim(self.xMinWithOffset, self.xMaxWithOffset)
        self.yMax = alignment.queryEndPosition if self.options.limitQueryToAlignedArea else query.length
        self.yMinWithOffset = self.yMin - offset
        self.yMaxWithOffset = self.yMax + offset
        self.axes.set_ylim(self.yMinWithOffset, self.yMaxWithOffset)
        self.plotAreaMask = Rectangle((self.xMin + offset, self.yMin + offset),
                                      self.xMax - self.xMin - offset,
                                      self.yMax - self.yMin - offset,
                                      facecolor='none', edgecolor='none')
        self.axes.add_patch(self.plotAreaMask)
        self.axes.set_aspect("equal")

    def __plotReference(self, alignment: AlignmentResultRow, reference: OpticalMap):
        self.axes.set_xlabel(f"Reference {reference.moleculeId}")
        referenceLabelsInScope = [p for p in reference.getPositionsWithSiteIds() if
                                  self.xMin <= p.position <= alignment.referenceEndPosition]
        self.axes.plot([r.position for r in referenceLabelsInScope],
                       np.repeat(self.yMin, len(referenceLabelsInScope)),
                       marker="|",
                       markersize=16,
                       markeredgewidth="2", linewidth=16, markeredgecolor="black",
                       color="yellow")

        for r in self.__skipDensePositions(referenceLabelsInScope):
            self.axes.annotate(r.siteId, (r.position, self.yMin),
                               textcoords="offset points",
                               xytext=(0, -10),
                               ha="center",
                               va="top",
                               rotation=90)

    def __plotQuery(self, alignment: AlignmentResultRow, query: OpticalMap):
        self.axes.set_ylabel(f"Query {query.moleculeId}")
        queryLabelsInScope = [p for p in query.getPositionsWithSiteIds() if
                              not self.options.limitQueryToAlignedArea
                              or self.yMin <= p.position <= alignment.queryEndPosition]

        self.axes.plot(np.repeat(self.xMin, len(queryLabelsInScope)), [q.position for q in queryLabelsInScope],
                       marker="_",
                       markersize=16,
                       markeredgewidth="2",
                       linewidth=16,
                       markeredgecolor="black",
                       color="lime")

        for q in self.__skipDensePositions(queryLabelsInScope):
            self.axes.annotate(q.siteId, (self.xMin, q.position),
                               textcoords="offset points",
                               xytext=(-15, 0),
                               ha="right",
                               va="center")

    def __plotSegments(self, alignment: AlignmentResultRow):
        groupedSegments = groupby(alignment.segments, lambda s: s.peak)
        colors = self.__getContrastingColors(len(alignment.segments))

        for (peakNumber, (peak, segments)), color in zip(enumerate(groupedSegments), colors):
            self.__drawPeak(color, peak)
            for segmentNumber, segment in enumerate(segments):
                x = list(map(lambda p: p.reference.position, segment.alignedPositions))
                y = list(map(lambda p: p.query.position, segment.alignedPositions))
                self.__plotSegment(color, peak, peakNumber, segment, segmentNumber, x, y)
                self.__drawGrid(x, y)

    def __drawPeak(self, color, peak: Peak):
        peakRectangle = Rectangle((peak.leftProminenceBasePosition, self.yMinWithOffset - 9999999999.),
                                  peak.width,
                                  self.yMaxWithOffset + 99999999999999.,
                                  color=color,
                                  alpha=0.2,
                                  angle=-45.,
                                  rotation_point=(peak.position, 0))  # type:ignore
        self.axes.add_patch(peakRectangle)
        peakRectangle.set_clip_path(self.plotAreaMask)

    def __drawPrimaryPeak(self, correlation: InitialAlignment):
        peak = correlation.maxPeak
        self.axes.plot([peak.position, self.xMax], [0, self.xMax - peak.position],
                       linestyle="dashdot",
                       marker=None,
                       color="black",
                       label="primary correlation")
        peakRectangle = Rectangle((peak.leftProminenceBasePosition, self.yMinWithOffset - 9999999999.),
                                  peak.width,
                                  self.yMaxWithOffset + 99999999999999.,
                                  color="wheat",
                                  alpha=0.5,
                                  angle=-45.,
                                  rotation_point=(peak.position, 0))  # type:ignore
        self.axes.add_patch(peakRectangle)
        peakRectangle.set_clip_path(self.plotAreaMask)

    def __plotSegment(self, color, peak: Peak, peakNumber: int, segment: AlignmentSegment, segmentNumber: int, x, y):
        self.axes.plot(x, y,
                       label=f" peak {peakNumber + 1} (height: {peak.height:.0f}), segment {segmentNumber + 1} "
                             f"(score: {segment.segmentScore:.1f})",
                       marker="+",
                       markersize=8,
                       markeredgecolor=color,
                       linewidth=2,
                       color=color)

    def __drawGrid(self, x, y):
        self.axes.vlines(x, self.yMin, y, linestyles="--", colors="black", alpha=0.5, linewidth=0.5)
        self.axes.hlines(y, self.xMin, x, linestyles="--", colors="black", alpha=0.5, linewidth=0.5)

    def __skipDensePositions(self, positions: List[PositionWithSiteId]):
        minDistance = (self.xMax - self.xMin) / 150
        iterator = iter(positions)
        currentPosition = next(iterator)
        previousPosition: PositionWithSiteId | None = None
        while currentPosition is not None:
            if not previousPosition or currentPosition.position - previousPosition.position >= minDistance:
                yield currentPosition
                previousPosition = currentPosition
            currentPosition = next(iterator, None)

    @staticmethod
    def __getContrastingColors(count: int):
        colorMap = pyplot.get_cmap("plasma")
        contrasting = np.column_stack((np.linspace(0, .5, ceil(count / 2)),
                                       np.linspace(.5, 1, ceil(count / 2)))).flatten()
        return colorMap(contrasting)
