
Scripts and data in this directory are used to perform resolver benchmarking.
They have been extracted from a real studio, and anonymized.

Usage:

```
]$ rez-python ./benchmark.py
```

Results are written to a temporary `./results` directory.

You should run benchmarking on new code that you expect to perform better (eg a
change to the solver algorithm), and run it on the existing master also. You
then compare the results like so:

```
]$ rez-python ./benchmark.py --compare ./results ./other_results
```

If your results are objectively better than the previous results (due to a
change to the resolver algorithm, for example), you should update the contents
of `./latest_results` accordingly, and put in a PR. Someone else should verify
the results before approving the PR.

You cannot simply compare performance to `./latest_results` because it may have
been run on a different macnine with different resources. However, it's worth
doing to check that the resolves themselves are identical. A change could
indicate a regression in the solver.
