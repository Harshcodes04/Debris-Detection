# Model evaluation — ghostgear_v1

Per-image evaluation of the ghost-gear detector on its held-out test split.
Recorded so the numbers in the demo and the presentation are traceable to a run,
not quoted from training logs.

## What was tested

| | |
|---|---|
| Model | `ghostgear_model.pt` (YOLOv8s, stage 3 of staged transfer) |
| Test set | 398 images, 567 annotated crab pots |
| Source | Ghost Pot Side-Scan Sonar Detection Dataset (PING Ecosystem, CC-BY-SA-4.0) |
| Threshold | conf 0.20 — the operating point `pipeline.py` runs at |
| Match rule | IoU >= 0.50 against ground truth |

Splits divide by survey recording, not randomly. Consecutive side-scan frames
are near-duplicates of each other, so a random split leaks training frames into
test and inflates the score. No test image shares a recording with training.

## Headline result

| Metric | Value |
|---|---|
| Precision | 0.416 (187 of 449 detections were real) |
| Recall | 0.330 (187 of 567 targets found) |
| F1 | 0.368 |
| False positives | 262 |
| False negatives | 380 |

## Per-image outcome

The aggregate averages over images that behaved very differently. Sorting each
of the 398 into a single outcome:

| Outcome | Images | Share |
|---|---:|---:|
| Missed entirely — no detection at all | 114 | 28.6% |
| Wrong place — boxed, but not on a target | 82 | 20.6% |
| Partial — found some, missed others | 60 | 15.1% |
| Correct reject — empty seabed, nothing flagged | 45 | 11.3% |
| Hit plus false alarm | 42 | 10.6% |
| Perfect — every target, nothing spurious | 36 | 9.0% |
| False alarm on empty seabed | 19 | 4.8% |

Only 36 images in 398 came out clean. The largest single group produced no
detection whatsoever — not a weak one a looser threshold would recover.

## Confidence does not separate right from wrong

| Detections | Median confidence | Maximum |
|---|---:|---:|
| Correct (matched a real pot) | 0.278 | 0.493 |
| All detections | 0.288 | 0.541 |

Correct detections score marginally *lower* than the population as a whole.
Consequences:

- The score cannot be used to rank candidates for an analyst to review.
- Raising the threshold discards true and false detections at close to the same
  rate, so there is little precision to buy.
- Nothing on this split exceeded 0.541, so there is no high-confidence tier.

This is the most significant finding in the per-image data and it is invisible
in mAP.

## Recall against target size

Median longest edge of the ground-truth box, in source pixels.

| Band | Targets | Found | Recall |
|---|---:|---:|---:|
| under 40 px | 146 | 60 | 41% |
| 40–80 px | 290 | 66 | 23% |
| 80–150 px | 125 | 55 | 44% |
| over 150 px | 6 | 6 | 100% |

This does **not** support "small objects are harder". If it did, recall would
climb steadily with size; instead the worst band is the middle one. The six
targets over 150 px are too few to read anything into. This is consistent with
the 1280 px retrain scoring worse than the 640 px model (mAP50 0.248 vs 0.310) —
resolution is not the binding constraint.

## Behaviour on empty seabed

64 of the 398 images contain no pot. These test the discrimination the problem
statement actually asks for — man-made object versus natural seafloor.

| Measure | Value |
|---|---|
| Correctly rejected | 45 / 64 (70%) |
| False boxes raised | 27 (0.42 per empty image) |

Recall is flat with scene density — 30% on images with one target, 34% with two,
35% with three or more — so the model is not being overwhelmed by clutter.

## Honest reading

The model is a **candidate generator, not a detector**. With four in ten flagged
objects real and a third of gear found, it is defensible as a first pass that
narrows an analyst's search, and not defensible as anything acted on without
review. The demo and the UI present it that way.

## Where the remaining recall is

The 114 silent misses are the target, not the low-confidence detections. The
standard remedy is to stop scoring frames in isolation: a pot on the seabed
appears in several consecutive pings, and often on both port and starboard
channels, so aggregating detections along the survey track gives each object
several chances to be seen. The registry in `ml/registry.py` already reconciles
detections across surveys by position; extending the same idea within a single
survey line is the next step.

Confidence calibration is the other open item — until the score separates
correct from incorrect, threshold tuning has nothing to work with.

## Reproducing

From this folder, against a YOLO-format copy of the dataset:

```
python -m ml.eval.per_image --data path/to/crabpot_yolo --model ghostgear_model.pt
```

Writes a CSV with one row per image: truth count, prediction count, TP/FP/FN,
best confidence, mean matched confidence, median target size, and the outcome
label used in the table above. `--conf` and `--iou` override the defaults.

## Context — the three training stages

| Stage | Model | Data | mAP50 |
|---|---|---|---:|
| 1 | `debris_fls_v1` | Marine Debris FLS (water tank) | 0.988 |
| 2 | `sidescan_v1` | SCTD wrecks/aircraft | 0.625 |
| 3 | `ghostgear_v1` | Ghost Pot SSS | 0.310 |

Stage 1's 0.988 is not a real-world figure — that dataset is a controlled water
tank with clean backgrounds. It is useful as a starting point for the transfer,
not as evidence of field performance. The number that matters is stage 3's.
