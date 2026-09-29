# Pilot batch summary

20 bundles generated, 20 valid against the Evidence Bundle Schema. Generators: {'qwen3.8:27b': 15, 'gemma4:31b': 5}.

## identity

Scored by both teachers: 20. INSUFFICIENT_EVIDENCE: 0. Failed: 0.

- Teacher agreement: mean |median difference| 2.10; exact agreement on 1/20; within 1 on 8/20.
- Within-teacher spread across samples (max - min): mean 1.23.
- Median score histogram (both teachers pooled): 1:11 2:1 3:3 4:5 5:2 6:3 7:5 8:7 9:1 10:2

| bundle | ctx | gw | user | privileged | mounts | creds (class/prov) | qwen3.8:27b | gemma4:31b |
|---|---|---|---|---|---|---|---|---|
| bnd-syn-0000-978906 | C |  | non_root | y | data_rw | none | 7 (8,7,7) | 10 (10,10,10) |
| bnd-syn-0001-71b35c | A |  | non_root |  | kube_sa_token, run_secrets_ro | none | 7 (5,8,7) | 8 (8,8,8) |
| bnd-syn-0002-e58dcb | C | y | root |  | data_rw, host_etc, host_root | ref/injected | 3 (5,3,3) | 1 (1,1,1) |
| bnd-syn-0003-58db79 | C |  | non_root | y | docker_socket, kube_sa_token | plaintext/injected, ref/injected, ref/injected, plaintext/baked | 4 (7,2,4) | 1 (1,1,1) |
| bnd-syn-0004-506300 | A |  | root |  | data_rw, docker_socket | plaintext/injected, ref/injected, mount/injected, ref/injected | 4 (7,4,3) | 1 (1,1,1) |
| bnd-syn-0005-3cb433 | D |  | non_root |  | none | plaintext/baked, mount/baked | 7 (8,7,6) | 8 (8,8,8) |
| bnd-syn-0006-313416 | A |  | non_root |  | data_ro, tmp_scratch | none | 7 (4,7,7) | 8 (9,8,8) |
| bnd-syn-0007-9ae1ac | E | y | root |  | host_root | mount/baked, plaintext/injected | 3 (3,6,2) | 1 (1,1,1) |
| bnd-syn-0008-a92416 | E |  | non_root | y | data_rw | plaintext/baked, ref/baked, ref/baked, plaintext/baked | 6 (6,6,2) | 5 (5,5,5) |
| bnd-syn-0009-8c8243 | A |  | root | y | none | mount/injected | 4 (4,4,3) | 1 (1,1,1) |
| bnd-syn-0010-2774bd | E | y | non_root |  | none | ref/injected | 8 (8,8,9) | 8 (8,8,8) |
| bnd-syn-0011-090b0b | D |  | non_root |  | host_root | ref/baked, mount/injected, ref/injected, plaintext/injected | 6 (6,5,7) | 1 (1,1,1) |
| bnd-syn-0012-f8fc76 | D |  | root |  | run_secrets_ro | ref/injected, plaintext/injected, ref/injected, plaintext/injected | 6 (6,3,7) | 8 (8,8,7) |
| bnd-syn-0013-8a8fde | D |  | root | y | docker_socket, host_root | plaintext/baked, plaintext/baked, plaintext/injected | 2 (2,2,2) | 1 (1,1,1) |
| bnd-syn-0014-6113ae | A |  | root | y | host_root, tmp_scratch | mount/injected, mount/baked, mount/injected, mount/baked | 3 (3,3,4) | 1 (1,1,1) |
| bnd-syn-0015-369ada | C |  | non_root | y | docker_socket, kube_sa_token, run_secrets_ro | plaintext/baked, ref/baked, plaintext/injected | 4 (3,5,4) | 1 (1,1,1) |
| bnd-syn-0016-5a2d93 | A |  | non_root | y | data_ro, docker_socket | mount/injected | 4 (2,6,4) | 1 (1,1,1) |
| bnd-syn-0017-9e7c8b | C |  | non_root |  | data_ro, data_rw | none | 9 (9,9,8) | 10 (10,10,10) |
| bnd-syn-0018-a8a3bb | B |  | non_root |  | none | mount/injected, ref/injected, plaintext/injected | 7 (7,7,7) | 8 (8,8,9) |
| bnd-syn-0019-7135a7 | A |  | non_root |  | data_ro, docker_socket, host_etc | ref/baked, ref/injected, mount/injected, plaintext/injected | 5 (4,6,5) | 1 (1,1,1) |

## containment

Scored by both teachers: 12. INSUFFICIENT_EVIDENCE: 8. Failed: 0.

- Teacher agreement: mean |median difference| 0.92; exact agreement on 6/12; within 1 on 9/12.
- Within-teacher spread across samples (max - min): mean 0.71.
- Median score histogram (both teachers pooled): 1:9 2:3 3:5 4:3 5:3 6:1

| bundle | ctx | gw | user | privileged | mounts | creds (class/prov) | qwen3.8:27b | gemma4:31b |
|---|---|---|---|---|---|---|---|---|
| bnd-syn-0000-978906 | C |  | non_root | y | data_rw | none | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0001-71b35c | A |  | non_root |  | kube_sa_token, run_secrets_ro | none | 6 (5,6,8) | 5 (5,5,5) |
| bnd-syn-0002-e58dcb | C | y | root |  | data_rw, host_etc, host_root | ref/injected | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0003-58db79 | C |  | non_root | y | docker_socket, kube_sa_token | plaintext/injected, ref/injected, ref/injected, plaintext/baked | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0004-506300 | A |  | root |  | data_rw, docker_socket | plaintext/injected, ref/injected, mount/injected, ref/injected | 1 (1,1,1) | 1 (1,1,1) |
| bnd-syn-0005-3cb433 | D |  | non_root |  | none | plaintext/baked, mount/baked | 3 (4,3,3) | 3 (3,3,2) |
| bnd-syn-0006-313416 | A |  | non_root |  | data_ro, tmp_scratch | none | 3 (3,3,3) | 3 (3,3,3) |
| bnd-syn-0007-9ae1ac | E | y | root |  | host_root | mount/baked, plaintext/injected | 5 (5,3,5) | 1 (1,1,1) |
| bnd-syn-0008-a92416 | E |  | non_root | y | data_rw | plaintext/baked, ref/baked, ref/baked, plaintext/baked | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0009-8c8243 | A |  | root | y | none | mount/injected | 2 (3,2,2) | 1 (1,1,1) |
| bnd-syn-0010-2774bd | E | y | non_root |  | none | ref/injected | 4 (4,5,4) | 2 (2,2,2) |
| bnd-syn-0011-090b0b | D |  | non_root |  | host_root | ref/baked, mount/injected, ref/injected, plaintext/injected | 2 (4,1,2) | 1 (1,1,1) |
| bnd-syn-0012-f8fc76 | D |  | root |  | run_secrets_ro | ref/injected, plaintext/injected, ref/injected, plaintext/injected | 5 (6,5,5) | 3 (3,3,3) |
| bnd-syn-0013-8a8fde | D |  | root | y | docker_socket, host_root | plaintext/baked, plaintext/baked, plaintext/injected | 1 (1,1,0) | 1 (1,1,1) |
| bnd-syn-0014-6113ae | A |  | root | y | host_root, tmp_scratch | mount/injected, mount/baked, mount/injected, mount/baked | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0015-369ada | C |  | non_root | y | docker_socket, kube_sa_token, run_secrets_ro | plaintext/baked, ref/baked, plaintext/injected | 1 (1,2,1) | 1 (1,1,1) |
| bnd-syn-0016-5a2d93 | A |  | non_root | y | data_ro, docker_socket | mount/injected | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0017-9e7c8b | C |  | non_root |  | data_ro, data_rw | none | 4 (5,3,4) | 4 (4,4,4) |
| bnd-syn-0018-a8a3bb | B |  | non_root |  | none | mount/injected, ref/injected, plaintext/injected | INSUFF (permissions, mounts) | INSUFF (permissions, mounts) |
| bnd-syn-0019-7135a7 | A |  | non_root |  | data_ro, docker_socket, host_etc | ref/baked, ref/injected, mount/injected, plaintext/injected | INSUFF (permissions) | INSUFF (permissions) |

The scenario columns are the generator's facts, shown here for review only; the labellers never saw them. Where a bundle hid a fact (a BLIND or PARTIAL attribute), the labeller could not see it either.
