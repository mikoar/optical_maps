import os.path
from typing import List

import pandas as pd
from pandas import Series, DataFrame

from src.alignment.alignment_results import AlignmentResults
from src.correlation.bionano_alignment import BionanoAlignment
from src.parsers.bionano_file_reader import BionanoFileReader


class XmapReader:
    def __init__(self) -> None:
        self.reader = BionanoFileReader()

    def readAlignments(self, filePath: str, alignmentIds=None, queryIds=None) -> List[BionanoAlignment]:
        alignments = self.reader.readFile(filePath,
                                          ["XmapEntryID", "QryContigID", "RefContigID", "QryStartPos",
                                           "QryEndPos", "RefStartPos", "RefEndPos", "Orientation",
                                           "Confidence", "HitEnum", "QryLen", "RefLen", "Alignment"])
        if alignmentIds:
            alignments = alignments[alignments["XmapEntryID"].isin(alignmentIds)]

        if queryIds:
            alignments = alignments[alignments["QryContigID"].isin(queryIds)]

        return alignments.apply(self.__parseRow, axis=1).tolist()

    @staticmethod
    def writeAlignments(filePath: str, alignmentResults: AlignmentResults):
        with open(filePath, mode='w') as file:
            columns = {
                "#h": "#f",
                "XmapEntryID": "int",
                "QryContigID": "int",
                "RefContigID": "int",
                "QryStartPos": "float",
                "QryEndPos": "float",
                "RefStartPos": "float",
                "RefEndPos": "float",
                "Orientation": "string",
                "Confidence": "float",
                "HitEnum": "string",
                "QryLen": "float",
                "RefLen": "float",
                "LabelChannel": "int",
                "Alignment": "string"
            }
            file.write("# XMAP File Version:\t0.2\n")
            file.write(f"# Reference Maps From:\t{os.path.abspath(alignmentResults.referenceFilePath)}\n")
            file.write(f"# Query Maps From:\t{os.path.abspath(alignmentResults.queryFilePath)}\n")
            file.write("\t".join([columnName for columnName in columns.keys()]) + "\n")
            file.write("\t".join([columnType for columnType in columns.values()]) + "\n")

            dataFrame = DataFrame([{
                "QryContigID": row.queryId,
                "RefContigID": row.referenceId,
                "QryStartPos": "{:.1f}".format(row.queryStartPosition),
                "QryEndPos": "{:.1f}".format(row.queryEndPosition),
                "RefStartPos": "{:.1f}".format(row.referenceStartPosition),
                "RefEndPos": "{:.1f}".format(row.referenceEndPosition),
                "Orientation": "-" if row.reverseStrand else "+",
                "Confidence": "{:.2f}".format(row.confidence),
                "HitEnum": row.cigarString,
                "QryLen": "{:.1f}".format(row.queryLength),
                "RefLen": "{:.1f}".format(row.referenceLength),
                "LabelChannel": 1,
                "Alignment": "".join(
                    [f"({pair.referencePositionIndex},{pair.queryPositionIndex})" for pair in row.alignedPairs]),
            } for row in alignmentResults.rows], index=pd.RangeIndex(start=1, stop=len(alignmentResults.rows) + 1))

            dataFrame.to_csv(file, sep='\t', header=False, mode="a", line_terminator="\n")

    @staticmethod
    def __parseRow(row: Series):
        return BionanoAlignment.parse(row["XmapEntryID"], row["QryContigID"], row["RefContigID"], row["QryStartPos"],
                                      row["QryEndPos"], row["RefStartPos"], row["RefEndPos"], row["Orientation"],
                                      row["Confidence"], row["HitEnum"], row["QryLen"], row["RefLen"], row["Alignment"])
