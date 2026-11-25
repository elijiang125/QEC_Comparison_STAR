"""Where every qubit of a bicycle-chain code block lives (plan step 2).

A block on an l x m torus uses four l x m arrays of qubits:

    data, left half    indices [0,        l*m)
    data, right half   indices [l*m,    2*l*m)
    X-check ancillas   indices [2*l*m,  3*l*m)   one per check position (i, j)
    Z-check ancillas   indices [3*l*m,  4*l*m)

Inside each array, torus cell (i, j) sits at offset i*m + j, the same
convention as `codes.cell`. So X-check (i, j) is row i*m + j of H.

A monomial x^p y^q acts on positions as a slide: (i, j) -> (i+p, j+q),
wrapping around the torus. On neutral-atom hardware this is literally
moving a whole array of atoms by (p, q) lattice sites.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Layout:
    l: int
    m: int

    @property
    def n_half(self):
        """Qubits in one l x m array (21 for the [[42,6,6]] code)."""
        return self.l * self.m

    @property
    def num_qubits(self):
        """All qubits in the block: 2 data halves + 2 ancilla arrays."""
        return 4 * self.n_half

    def cells(self):
        """All torus positions (i, j), in row-major order."""
        return [(i, j) for i in range(self.l) for j in range(self.m)]

    def cell(self, i, j):
        """Offset of position (i, j) inside one array, wrapping around the torus."""
        return (i % self.l) * self.m + (j % self.m)

    def slide(self, i, j, mono, sign=1):
        """Slide position (i, j) by the monomial x^p y^q (or its inverse if sign=-1)."""
        p, q = mono
        return ((i + sign * p) % self.l, (j + sign * q) % self.m)

    def data(self, half, i, j):
        """Data qubit at (i, j) in the left ('L') or right ('R') half."""
        if half not in ("L", "R"):
            raise ValueError(f"half must be 'L' or 'R', got {half!r}")
        return (0 if half == "L" else self.n_half) + self.cell(i, j)

    def x_anc(self, i, j):
        """Ancilla that measures X-check (i, j)."""
        return 2 * self.n_half + self.cell(i, j)

    def z_anc(self, i, j):
        """Ancilla that measures Z-check (i, j)."""
        return 3 * self.n_half + self.cell(i, j)

    def coords(self, q):
        """(x, y) drawing coordinates, so Stim's diagrams show the four arrays side by side."""
        block, c = divmod(q, self.n_half)
        i, j = divmod(c, self.m)
        return (block * (self.m + 1) + j, i)
