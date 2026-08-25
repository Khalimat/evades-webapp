# Data directory

This folder is bind-mounted into both the `api` and `worker` containers
at `/data`. Nothing here gets baked into a Docker image, so you can
update the databases without rebuilding anything — just replace the
files and restart the `worker` service.

## Layout to create

```
data/
├── hmm/
│   └── evades_profiles.hmm          # concatenated HMM library, then hmmpress'd
├── foldseek/
│   └── evades_structures_db*        # output of `foldseek createdb`, built from
│                                     # foldseek_monomer_structures/ below — NOT
│                                     # from generator/assets/structures/EVADES_v1/
├── foldseek_monomer_structures/     # one PDB/mmCIF file per protein, single
│                                     # chain only — the Foldseek DB's source.
│                                     # See "Monomer vs. multimer structures"
│                                     # below before touching this.
├── uploads/                         # auto-created, holds user uploads (temporary)
└── downloads/                       # served statically at /downloads/ by nginx
    ├── hmm_profiles.tar.gz
    ├── predicted_structures.tar.gz  # multimer/complex structures — see below
    ├── sequences.fasta
    └── metadata.tsv
```

## Monomer vs. multimer structures — don't mix these up

`data/foldseek_monomer_structures/` and `generator/assets/structures/EVADES_v1/`
(the source for `predicted_structures.tar.gz`, per-protein `download.zip`
bundles, and the Explore pages) are **deliberately different sets**, and
the Foldseek DB must only ever be built from the monomer one.

Several proteins (e.g. `gp5_9`, `acric5`) were predicted in complex with
their binding partner (e.g. `gp5_9` with RecBCD, since it's a RecBCD
inhibitor) — genuinely useful to show on the website, since the whole
point is the protein's mechanism of action. But `foldseek createdb`
indexes every chain in a structure file separately, and the search
result's chain-collapsing logic (`_base_protein_name` in
`backend/app/tasks.py`) folds any `<protein>_<chain>` target name back
down to `<protein>`. Build the Foldseek DB from a multimer file and a
query that happens to match the *embedded partner protein* — not the
EVADES protein at all — gets reported as a hit against that protein.
This actually happened: `data/foldseek/evades_structures_db` was once
built from the multimer set, and a structure matching RecB (embedded in
`gp5_9`'s complex prediction) falsely matched `gp5_9`; multiple `acric*`
entries that happened to share a similar bound partner chain even
falsely cross-matched *each other*. `foldseek_monomer_structures/`
exists specifically to prevent this — one chain per protein, no
partners.

`backend/tests/test_structure_data_integrity.py` checks both directions
(the Foldseek source is single-chain everywhere; known-multimeric
proteins in the website/download source still have >1 chain) — run it
locally after touching either directory. It's gitignored data, so it
skips automatically in CI.

## Building the HMM database (once)

```bash
cat profiles/*.hmm > data/hmm/evades_profiles.hmm
hmmpress data/hmm/evades_profiles.hmm
```

This can be done on any machine with HMMER installed — your laptop,
the EBI cluster, wherever. Only the resulting files need to end up in
`data/hmm/`.

## Building the Foldseek database (once)

```bash
foldseek createdb data/foldseek_monomer_structures/ data/foldseek/evades_structures_db
```

`data/foldseek_monomer_structures/` should contain your 268 PDB/mmCIF
files, **one chain per file** — see "Monomer vs. multimer structures"
above for why. Same note as above — build anywhere with Foldseek
installed, then copy the output files here.

## Building on a Mac (for local testing)

You don't need Docker for this precompute step — installing the tools
directly via Homebrew is easiest:

```bash
brew install hmmer
brew install brewsci/bio/foldseek   # or: conda install -c bioconda foldseek
```

Then run the same two commands as above, directly on your Mac. Copy
the resulting files into `data/hmm/` and `data/foldseek/` — the Mac
build output is used the same way whether the search later runs in a
Linux container (arm64, on Apple Silicon) or on a cloud VM.

## Bulk download files

These are plain static files nginx serves directly — generate them
however is convenient (a script that tars up structures, concatenates
FASTAs, exports your metadata table to TSV) and drop them in
`data/downloads/`.
