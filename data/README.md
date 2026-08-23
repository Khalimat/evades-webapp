# Data directory

This folder is bind-mounted into both the `api` and `worker` containers
at `/data`. Nothing here gets baked into a Docker image, so you can
update the databases without rebuilding anything — just replace the
files and restart the `worker` service.

## Layout to create

```
data/
├── hmm/
│   └── evades_profiles.hmm      # concatenated HMM library, then hmmpress'd
├── foldseek/
│   └── evades_structures_db*    # output of `foldseek createdb`
├── uploads/                     # auto-created, holds user uploads (temporary)
└── downloads/                   # served statically at /downloads/ by nginx
    ├── hmm_profiles.tar.gz
    ├── predicted_structures.tar.gz
    ├── sequences.fasta
    └── metadata.tsv
```

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
foldseek createdb structures/ data/foldseek/evades_structures_db
```

`structures/` should contain your 268 PDB/mmCIF files. Same note as
above — build anywhere with Foldseek installed, then copy the output
files here.

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
