# %%
from random import Random
from typing import Dict, List

import numpy as np
import pandas as pd
from matplotlib import cycler  # type: ignore
from matplotlib import rcParams
from p_tqdm import p_map
from tqdm import tqdm

from src.correlation.bionano_alignment import BionanoAlignment
from src.correlation.optical_map import OpticalMap
from src.correlation.plot import plotHeatMap
from src.correlation.sequence_generator import SequenceGenerator
from src.correlation.validator import Validator
from src.parsers.cmap_reader import CmapReader
from src.parsers.xmap_reader import XmapReader

rcParams["lines.linewidth"] = 1
rcParams['axes.prop_cycle'] = cycler(color=["#e74c3c"])


def getWorkerInputs(alignments: List[BionanoAlignment], reference: np.ndarray, queries: List[OpticalMap],
                    resolution: int, generator: SequenceGenerator):
    for alignment in alignments:
        yield (alignment,
               reference,
               next(q for q in queries if q.moleculeId == alignment.queryId),
               resolution,
               generator)


def alignmentsToDict(a: BionanoAlignment, score: float, resolution: int, blur: int, isValid: bool):
    return {
        'resolution': resolution,
        'blur': blur,
        'alignmentId': a.alignmentId,
        'queryId': a.queryId,
        'referenceId': a.referenceId,
        'confidence': a.confidence,
        'score': score,
        'reverseStrand': a.reverseStrand,
        'isValid': isValid
    }


indexCols = ['resolution', 'blur', 'alignmentId']


def initAlignmentsFile(file):
    pd.DataFrame(columns=[
        'resolution',
        'blur',
        'alignmentId',
        'queryId',
        'referenceId',
        'confidence',
        'score',
        'reverseStrand',
        'isValid'
    ]).set_index(indexCols).to_csv(file, mode='w')


def appendAlignmentsToFile(alignments: List[Dict], file):
    pd.DataFrame(alignments).set_index(indexCols).to_csv(file, mode='a', header=False)


def alignWithReference(input):
    alignment: BionanoAlignment
    reference: OpticalMap
    query: OpticalMap
    resolution: int
    generator: SequenceGenerator
    alignment, reference, query, resolution, generator = input
    peaks = query.getInitialAlignment(reference, generator, alignment.reverseStrand)
    validator = Validator(resolution)
    isMaxPeakValid = validator.validate(peaks.maxPeak, alignment)

    return 1 if isMaxPeakValid else 0, peaks.getRelativeScore(alignment, validator)


# %%


if __name__ == '__main__':
    baseDir = '.local_data/NA12878_BSPQI_pipeline_results/output/contigs/alignmolvref/merge/alignmolvref_contig21'
    alignmentsFile = f"{baseDir}.xmap"
    referenceFile = f"{baseDir}_r.cmap"
    queryFile = f"{baseDir}_q.cmap"
    # alignmentsFile = "data/NA12878_BSPQI/EXP_REFINEFINAL1.xmap"
    # referenceFile = "data/NA12878_BSPQI/hg19_NT.BSPQI_0kb_0labels.cmap"
    # queryFile = "data/NA12878_BSPQI/EXP_REFINEFINAL1.cmap"

    df = pd.DataFrame()

    alignmentReader = XmapReader()
    alignments = alignmentReader.readAlignments(alignmentsFile)
    alignmentsCount = len(alignments)
    resolutions = [128, 256, 512, 1024]
    blurs = [1, 2, 3, 4]  # [0, 2, 4, 8, 16]
    title = f"contig21_count_{alignmentsCount}_res_{','.join(str(x) for x in resolutions)}_blur_{','.join(str(x) for x in blurs)}"

    alignmentsResultFile = f"output_heatmap/result_{title}.csv"
    initAlignmentsFile(alignmentsResultFile)

    # %%

    isoResolutionResults = []
    with tqdm(total=alignmentsCount * len(blurs) * len(resolutions)) as progressBar:
        for resolution in resolutions:
            isoBlurResults = []
            for blur in blurs:
                reader = CmapReader()
                validAlignments = []
                validCount = 0
                sampledAlignments = [a for a in Random(123).sample([a for a in alignments], alignmentsCount)]
                referenceIds = set(map(lambda a: a.referenceId, sampledAlignments))
                alignmentsGroupedByReference = [[a for a in sampledAlignments if a.referenceId == r] for r in
                                                referenceIds]
                for alignmentsForReference, referenceId in zip(alignmentsGroupedByReference, referenceIds):
                    reference = reader.readReference(referenceFile, referenceId)
                    queries = reader.readQueries(queryFile, list(map(lambda a: a.queryId, alignmentsForReference)))
                    progressBar.set_description(
                        f"Resolution: {resolution}, blur: {blur}, {len(queries)} queries for reference {referenceId}")

                    poolResults = p_map(alignWithReference, list(
                        getWorkerInputs(alignmentsForReference, reference, queries, resolution,
                                        SequenceGenerator(resolution, blur))), num_cpus=8)
                    validationResults, scores = zip(*poolResults)

                    alignmentDataToStore = [alignmentsToDict(a, score, resolution, blur, validationResult)
                                            for a, score, validationResult in
                                            zip(alignmentsForReference, scores, validationResults)]

                    appendAlignmentsToFile(alignmentDataToStore, alignmentsResultFile)

                    validCount += sum(validationResults)
                    progressBar.update(len(alignmentsForReference))

                isoBlurResults.append(validCount / len(sampledAlignments) * 100)

            isoResolutionResults.append(isoBlurResults)

    plotHeatMap(isoResolutionResults, f"output_heatmap/heatmap_{title}.svg", blurs, resolutions)

# %%
# 1000 dobrze zmapowanych sekwencji
#  zbadać parametry - heat map, dobrać zakres parametrów tak żeby było widać spadek, do res * blur * 2 < 1000
# wynik: ile % wyników się pokrywa z ref aligner, druga heatmapa z czasami obliczeń
# potem przefiltrować cząsteczki i parametry, tak żeby zawsze mieć 100%, heat mapa parametry -> średnia/mediana score + odchylenie
# kolejny wykres x - jakość,  y - liczba cząsteczek o tej wartości jakości, kernel density

# TODO: contigi 21 w mniejszym zakresie blur, podesłać scatter ploty
