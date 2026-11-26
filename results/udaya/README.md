# Recorded results

One JSON object per line, one line per experiment cell. Field definitions are in
`docs/udaya/INTEGRATION.md`. Both files hold **provisional, decoder-dependent** data: neither uses
the paper's decoders, and the surface-code cells use Stim's generated circuit as a stand-in. None of
it is a reproduction of the paper's logical error rates.

| File | Decoder | Design | Cells | Code revision |
|---|---|---|---|---|
| `validation_tesseract.jsonl` | Tesseract (`det_beam=5`, `pqlimit=200000`), a heuristic at this beam | fixed number of shots, set before sampling | 12 | in each record: `code_revision` (commit `0f4322f`, source tree `f351cc7`) |
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

`decoder_low_weight_checks.jsonl` records the low-weight fault checks quoted in
`docs/udaya/VALIDATION.md`: decoder settings, circuit, fault weight, sample count, seed and the number
mis-corrected. It was produced with `experiments.low_weight_fault_failures` at commit `0f4322f`.

To regenerate the validation data (about 50 minutes on 12 cores; needs `pip install
tesseract-decoder`), write to a new file and compare. The runner refuses to add to an existing file,
because the seeds are deterministic and a second run would only duplicate the same trials:

```sh
python -m qec_star.hardware validate --out /tmp/validation_check.jsonl --workers 12
```

`runtime_seconds` is wall time on `sampling_plan.workers` processes, not CPU time.

Seeds depend only on the base seed, the circuit and the chunk index, so the same code revision and
package versions give the same counts on any number of workers.
