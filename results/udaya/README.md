# Recorded results

One JSON object per line, one line per experiment cell. Field definitions are in
`docs/udaya/INTEGRATION.md`. Both files hold **provisional, decoder-dependent** data: neither uses
the paper's decoders, and the surface-code cells use Stim's generated circuit as a stand-in. None of
it is a reproduction of the paper's logical error rates.

| File | Decoder | Design | Cells | Code revision |
|---|---|---|---|---|
| `validation_tesseract.jsonl` | Tesseract (`det_beam=5`, `pqlimit=200000`), a heuristic at this beam | fixed number of shots, set before sampling | 12 | in each record: `code_revision` (commit `0f4322f`, source tree `f351cc7`) |
| `validation_surface_team_tesseract.jsonl` | Tesseract, same settings | fixed number of shots (200,000 at d ≤ 5, 40,000 at d = 7, 9) | 15: the team's surface circuit at d = 3, 5, 7, 9, and Stim's circuit at d = 3 | commit `8dd53a5`, source tree `47d0bb4`; each record also has `loaded_source_sha256` |
| `pilot_bposd0_sequential.jsonl` | BP + OSD-0 from `ldpc`; about 100 times worse than Tesseract on the same bicycle circuits | sampling stopped at 100 failures or 40,000 shots | 19 of a planned 60 | commit `e8d1b06` (`source_commit` in each record; one batch shows `91d4123`, a documentation-only commit with identical package code) |

About the pilot file:

- It was stopped on purpose after 19 cells, once the decoder was shown to mis-correct low-weight
  faults that another decoder corrects. Finishing the grid would have produced more decoder-limited numbers.
- Its last record (surface d = 5, p = 2e-3) is complete; the cell that was running when it was
  stopped left no record.
- Because sampling stopped on a failure count, its `wilson95` intervals are nominal: the estimate
  is biased slightly upward and the interval can under-cover. With 100 failures the bias is about 1%.
- Its bicycle circuits are byte-identical to those in the validation file for the same scenario and
  basis (equal `circuit_sha256`), so the two files compare the decoders on the same circuits.
- It is kept as evidence of the decoder problem, not as a measurement of either code.

The `architecture` field says which surface circuit a record used: `surface` is the team's circuit
(`qec_star.surface`), `surface_reference` is Stim's generated circuit. Every surface record in the
two older files is `surface_reference`; they were made before the team's circuit existed and have
not been relabeled or rerun.

`decoder_low_weight_checks.jsonl` records the low-weight fault checks quoted in
`docs/udaya/VALIDATION.md`: decoder settings, circuit, fault weight, sample count, seed and the number
mis-corrected. It was produced with `experiments.low_weight_fault_failures` at commit `0f4322f`.

To regenerate the validation data (about 50 and 70 minutes on 12 cores; needs `pip install
tesseract-decoder`), write to a new file and compare. The runner refuses to add to an existing file,
because the seeds are deterministic and a second run would only duplicate the same trials:

```sh
python -m qec_star.hardware validate --grid baseline --out /tmp/baseline_check.jsonl --workers 12
python -m qec_star.hardware validate --grid surface  --out /tmp/surface_check.jsonl  --workers 12
```

`runtime_seconds` is wall time on `sampling_plan.workers` processes, not CPU time.

Seeds depend only on the base seed, the circuit and the chunk index, so the same code revision and
package versions give the same counts on any number of workers.
