# Benchmarking Results

This document contains historical benchmarking results. These measure the speed
of resolution of a list of predetermined requests. Do **NOT** change this file
by hand; the 'benchmark' Github workflow does this automatically.

| Rez | Python | Platform | CPU | #CPU | Median | Mean | StdDev |
|-----|--------|----------|-----|------|--------|------|--------|
| 2.78.0 | 2.7 | Linux-5.4.0-1040-azure-x86_64-with-debian-bullseye-sid | Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz | 2 | 0.06 | 0.10 | 0.11 |
| 2.78.0 | 3.7 | Linux-5.4.0-1040-azure-x86_64-with-debian-bullseye-sid | Intel(R) Xeon(R) Platinum 8171M CPU @ 2.60GHz | 2 | 0.07 | 0.09 | 0.10 |
| 2.78.0 | 2.7 | Linux-5.4.0-1040-azure-x86_64-with-debian-bullseye-sid | Intel(R) Xeon(R) CPU E5-2673 v3 @ 2.40GHz | 2 | 1.94 | 3.09 | 3.04 |
| 2.78.0 | 3.7 | Linux-5.4.0-1040-azure-x86_64-with-debian-bullseye-sid | Intel(R) Xeon(R) Platinum 8171M CPU @ 2.60GHz | 2 | 1.81 | 2.85 | 2.88 |
