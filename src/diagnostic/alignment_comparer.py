from __future__ import annotations

import statistics
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import List, Dict, TextIO

import pandas as pd
from pandas import DataFrame

from src.diagnostic.xmap_alignment import XmapAlignment, XmapAlignedPair


class AlignmentComparison:
    avgOverlappingAlignment1Coverage: float
    avgOverlappingAlignment2Coverage: float
    avgOverlappingIdentity: float
    overlapping: int
    nonOverlapping: int
    firstOnly: int
    secondOnly: int
    rows: List[AlignmentRowComparison]
    null: AlignmentComparison

    def __init__(self, avgAlignment1Coverage: float,
                 avgAlignment2Coverage: float,
                 avgIdentity: float,
                 overlapping: int,
                 nonOverlapping: int,
                 firstOnly: int,
                 secondOnly: int,
                 rows: List[AlignmentRowComparison]):
        self.avgOverlappingAlignment1Coverage = avgAlignment1Coverage
        self.avgOverlappingAlignment2Coverage = avgAlignment2Coverage
        self.avgOverlappingIdentity = avgIdentity
        self.overlapping = overlapping
        self.nonOverlapping = nonOverlapping
        self.firstOnly = firstOnly
        self.secondOnly = secondOnly
        self.rows = rows

    @staticmethod
    def create(rows: List[AlignmentRowComparison]):
        if not rows:
            return AlignmentComparison.null

        overlappingRows = [row for row in rows if row.overlapping]
        return AlignmentComparison(
            statistics.fmean(map(lambda row: row.alignment1Coverage, overlappingRows)) if overlappingRows else 0,
            statistics.fmean(map(lambda row: row.alignment2Coverage, overlappingRows)) if overlappingRows else 0,
            statistics.fmean(map(lambda row: row.identity, overlappingRows)) if overlappingRows else 0,
            len(overlappingRows),
            sum(1 for row in rows if row.type == AlignmentRowComparisonResultType.BOTH and not row.overlapping),
            sum(1 for row in rows if row.type == AlignmentRowComparisonResultType.FIRST_ONLY),
            sum(1 for row in rows if row.type == AlignmentRowComparisonResultType.SECOND_ONLY),
            rows)

    def write(self, file: TextIO):
        file.writelines([
            f"# AvgOverlappingAlignment1Coverage\t{self.avgOverlappingAlignment1Coverage}\n",
            f"# AvgOverlappingAlignment2Coverage\t{self.avgOverlappingAlignment2Coverage}\n",
            f"# AvgOverlappingIdentity\t{self.avgOverlappingIdentity}\n",
            f"# Overlapping\t{self.overlapping}\n",
            f"# NonOverlapping\t{self.nonOverlapping}\n",
            f"# FirstOnly\t{self.firstOnly}\n",
            f"# SecondOnly\t{self.secondOnly}\n"
        ])

        headers = [
            "#"
            "QryContigID",
            "RefContigID",
            "Type",
            "Identity",
            "Alignment1Coverage",
            "Alignment2Coverage",
            "Orientation",
            "Alignment1 (referenceID, referencePosition, queryID, queryPosition, distance)",
            "Alignment2 (referenceID, referencePosition, queryID, queryPosition, distance)"
        ]
        file.write("\t".join([header for header in headers]) + "\n")

        data = [[
            row.queryId,
            row.referenceId,
            row.type.name,
            "{:.3f}".format(row.identity),
            "{:.3f}".format(row.alignment1Coverage),
            "{:.3f}".format(row.alignment2Coverage),
            row.orientation,
            "".join(str(row.alignment1.alignedPairs)),
            "".join(str(row.alignment2.alignedPairs))
        ] for row in self.rows]

        dataFrame = DataFrame(data, columns=headers, index=pd.RangeIndex(start=1, stop=len(self.rows) + 1))
        dataFrame.to_csv(file, sep='\t', header=False, mode="a", lineterminator="\n")


class _NullAlignmentComparison(AlignmentComparison):
    def __init__(self):
        super().__init__(0., 0., 0., 0, 0, 0, 0, [])

    def write(self, file: TextIO):
        return


AlignmentComparison.null = _NullAlignmentComparison()


class AlignmentRowComparisonResultType(Enum):
    BOTH = 1,
    FIRST_ONLY = 2,
    SECOND_ONLY = 3


@dataclass
class AlignmentRowComparison:
    type: AlignmentRowComparisonResultType
    alignment1: XmapAlignment
    alignment2: XmapAlignment
    alignment1Coverage: float
    alignment2Coverage: float
    identity: float

    @property
    def queryId(self):
        return self.alignment1.queryId or self.alignment2.queryId

    @property
    def referenceId(self):
        return self.alignment1.referenceId or self.alignment2.referenceId

    @property
    def orientation(self):
        return self.alignment1.orientation \
            if self.alignment1.orientation == self.alignment2.orientation \
            else f"{self.alignment1.orientation}/{self.alignment2.orientation}"

    @property
    def overlapping(self):
        return self.identity > 0.

    @staticmethod
    def alignment1Only(alignment1: XmapAlignment):
        return AlignmentRowComparison(
            AlignmentRowComparisonResultType.FIRST_ONLY, alignment1, XmapAlignment.null, 0., 0., 0.)

    @staticmethod
    def alignment2Only(alignment2: XmapAlignment):
        return AlignmentRowComparison(
            AlignmentRowComparisonResultType.SECOND_ONLY, XmapAlignment.null, alignment2, 0., 0., 0.)


class AlignmentComparer:
    def __init__(self, rowComparer: AlignmentRowComparer):
        self.__rowComparer = rowComparer

    def compare(self, alignments1: List[XmapAlignment], alignments2: List[XmapAlignment]):
        alignments1Dict = self.__toDict(alignments1)
        alignments2Dict = self.__toDict(alignments2)
        comparedRows = [self.__rowComparer.compare(a1, alignments2Dict[key]) for key, a1 in alignments1Dict.items() if
                        key in alignments2Dict]
        alignments1OnlyRows = [AlignmentRowComparison.alignment1Only(a1) for a1
                               in self.__getNotMatchingAlignments(alignments1Dict, alignments2Dict)]
        alignments2OnlyRows = [AlignmentRowComparison.alignment2Only(a2) for a2
                               in self.__getNotMatchingAlignments(alignments2Dict, alignments1Dict)]
        return AlignmentComparison.create(comparedRows + alignments1OnlyRows + alignments2OnlyRows)

    @staticmethod
    def __toDict(alignments: List[XmapAlignment]) -> Dict[(int, int), XmapAlignment]:
        return {(a.queryId, a.referenceId): a for a in sorted(alignments, key=lambda a: (a.referenceId, a.queryId))}

    @staticmethod
    def __getNotMatchingAlignments(source: Dict[(int, int), XmapAlignment], target: Dict[(int, int), XmapAlignment]):
        return [a1 for key, a1 in source.items() if key not in target]


class AlignmentRowComparer:
    def compare(self, alignment1: XmapAlignment, alignment2: XmapAlignment):
        coverage1 = self.__getCoverage(alignment1.alignedPairs, alignment2.alignedPairs)
        coverage2 = self.__getCoverage(alignment2.alignedPairs, alignment1.alignedPairs)

        ratio = self.__getIdentityRatio(alignment1, alignment2)
        return AlignmentRowComparison(
            AlignmentRowComparisonResultType.BOTH, alignment1, alignment2, coverage1, coverage2, ratio)

    @staticmethod
    def __getIdentityRatio(referenceAlignmentRow: XmapAlignment, actualAlignmentRow: XmapAlignment):
        matcher = SequenceMatcher(None, referenceAlignmentRow.alignedPairs, actualAlignmentRow.alignedPairs)
        ratio = matcher.ratio()
        return ratio

    @staticmethod
    def __getCoverage(pairs: List[XmapAlignedPair], otherPairs: List[XmapAlignedPair]):
        pairsLength = len(pairs)
        return (pairsLength - len(set(pairs).difference(set(otherPairs)))) / pairsLength if pairsLength > 0 else 1.
