# 02 - Bicycle-chain code: first numerical checks

Code: `qec_star.codes.bicycle_chain(l, m)`, with a(x,y) = 1 + y^3 + x y^2 + x y^4,
H = [A | A^T], Hx = Hz = H (self-dual). Qubit (half, i, j) has index
`half_offset + i*m + j`, where i is the x-exponent (0..l-1) and j is the y-exponent (0..m-1).

Tests: `tests/test_codes.py` (run `.venv/bin/pytest`, and `.venv/bin/pytest -m slow` for the distance check).

## Parameters

| l | m | n  | rank H | k | paper           |
|---|---|----|--------|---|-----------------|
| 3 | 7 | 42 | 18     | 6 | [[42, 6, 6]]    |
| 4 | 7 | 56 | 24     | 8 | [[14l, 2l, 6]]  |
| 3 | 11| 66 | 30     | 6 | [[66, 6, 8]]    |
| 3 | 13| 78 | 36     | 6 | [[78, 6, 10]]   |

Every check has weight 8, H H^T = 0 mod 2. k = 2l also holds for l = 2..5 at m = 7.
Distance was only checked for [[42, 6, 6]] (below).

## 1. Disjoint logical basis: a slice is a ROW (fixed i)

I tried every subset of every slice, for l = 3 and l = 4, m = 7:

```
slice type                  qubits   logicals found
row  {(i, j) : all j}         m=7    exactly 1: the whole row (weight 7)
col  {(i, j) : all i}         l      none
```

So the slices run along the **y (j) direction**: fix the x-exponent i, take all m cells.
That gives 2l logicals: rows L0..L_{l-1} on the left half and R0..R_{l-1} on the right half.

- Weight m (7 here; 11 and 13 for the other codes), which is odd. Rows of length 11 and 13 also work.
- The supports are pairwise disjoint.
- The overlap-parity matrix (X on one row vs Z on another) is the 2l x 2l identity,
  and the rows are independent modulo stabilizers. So they form a valid symplectic basis:
  logical qubit a has X̄_a = X(row a) and Z̄_a = Z(row a), with the same support.

Why it works:
- **It commutes with every check.** In polynomial language a row is x^i (1 + y + ... + y^{m-1}).
  Multiplying by any y^q does not change the all-ones sum, so
  a · row = x^i Σy · (1 + 1 + x + x) = 0 mod 2.
  This works because a(x,y) has an even number of terms for each power of x (two with x^0, two with x^1).
  A column, Σ_i x^i, fails: a · column = Σx · (1 + y^3 + y^2 + y^4), which is not 0.
- **It is not a stabilizer.** Odd weight means X(row) and Z(row) anticommute. A stabilizer commutes with everything that
  commutes with the checks, so the row cannot be a stabilizer.

## 2. Shift automorphism

(i, j) -> (i+1, j) on both halves maps every check to a sum of checks, so rowspace(H) is preserved.
This is because A and A^T are polynomials in x and y, and those commute with the shift x.
The shift acts on the logical basis as two separate l-cycles:

```
L0 -> L1 -> ... -> L_{l-1} -> L0      (left half)
R0 -> R1 -> ... -> R_{l-1} -> R0      (right half)
```

It moves the supports exactly, not just up to stabilizers. This matches the paper's
"1D cyclic shift on the left and right logicals separately". For contrast, (i, j) -> (i, j+1) is also an
automorphism, but it fixes every row logical.

## 3. Distance of [[42, 6, 6]]

Brute force with `gf2.low_weight_logicals`. Weights 1-5 take about 1 s, and the full weight-6 count takes about 4 s:

| weight | supports checked | non-trivial logicals |
|--------|------------------|----------------------|
| 1-5    | 974,981        | 0                    |
| 6      | 5,245,786        | 84                   |

Example weight-6 logical (half, i, j): (L,0,0) (L,0,1) (L,1,3) (R,1,0) (R,2,2) (R,2,3).
It mixes both halves and several rows. The minimum-weight logicals are even-weight and are
not the slice logicals, which have weight 7.

So d = 6, as the paper says. Because Hx = Hz, the X and Z distances are equal.

## Disagreements with the paper

None so far. The only ambiguity was the slice direction, and it is settled: rows (fixed i, length m).
