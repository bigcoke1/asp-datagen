# Pilot batch summary

20 bundles generated, 20 valid against the Evidence Bundle Schema. Generators: {'qwen2.5:7b': 15, 'mistral-nemo': 5}.

## identity

Scored by both teachers: 20. INSUFFICIENT_EVIDENCE: 0. Failed: 0.

- Teacher agreement: mean |median difference| 1.75; exact agreement on 6/20; within 1 on 15/20.
- Within-teacher spread across samples (max - min): mean 1.52.
- Median score histogram (both teachers pooled): 2:4 3:1 6:1 7:11 8:18 9:5

| bundle | ctx | gw | user | privileged | mounts | creds (class/prov) | qwen2.5:7b | mistral-nemo |
|---|---|---|---|---|---|---|---|---|
| bnd-syn-0000-978906 | C |  | non_root | y | data_rw | none | 8 (8,8,8) | 9 (9,9,8) |
| bnd-syn-0001-71b35c | A |  | non_root |  | kube_sa_token, run_secrets_ro | none | 2 (2,2,1) | 9 (9,6,9) |
| bnd-syn-0002-e58dcb | C | y | root |  | data_rw, host_etc, host_root | ref/injected | 8 (8,8,8) | 7 (7,9,7) |
| bnd-syn-0003-58db79 | C |  | non_root | y | docker_socket, kube_sa_token | plaintext/injected, ref/injected, ref/injected, plaintext/baked | 8 (8,8,8) | 7 (7,7,8) |
| bnd-syn-0004-506300 | A |  | root |  | data_rw, docker_socket | plaintext/injected, ref/injected, mount/injected, ref/injected | 8 (8,8,6) | 8 (7,8,8) |
| bnd-syn-0005-3cb433 | D |  | non_root |  | none | plaintext/baked, mount/baked | 8 (8,8,10) | 8 (9,8,8) |
| bnd-syn-0006-313416 | A |  | non_root |  | data_ro, tmp_scratch | none | 2 (2,2,1) | 7 (7,7,5) |
| bnd-syn-0007-9ae1ac | E | y | root |  | host_root | mount/baked, plaintext/injected | 8 (8,8,8) | 8 (8,8,9) |
| bnd-syn-0008-a92416 | E |  | non_root | y | data_rw | plaintext/baked, ref/baked, ref/baked, plaintext/baked | 8 (8,8,10) | 7 (8,7,7) |
| bnd-syn-0009-8c8243 | A |  | root | y | none | mount/injected | 2 (2,2,2) | 7 (9,7,7) |
| bnd-syn-0010-2774bd | E | y | non_root |  | none | ref/injected | 8 (8,8,8) | 8 (8,9,7) |
| bnd-syn-0011-090b0b | D |  | non_root |  | host_root | ref/baked, mount/injected, ref/injected, plaintext/injected | 8 (8,8,8) | 7 (6,7,8) |
| bnd-syn-0012-f8fc76 | D |  | root |  | run_secrets_ro | ref/injected, plaintext/injected, ref/injected, plaintext/injected | 8 (8,8,10) | 9 (9,9,8) |
| bnd-syn-0013-8a8fde | D |  | root | y | docker_socket, host_root | plaintext/baked, plaintext/baked, plaintext/injected | 8 (2,8,8) | 7 (7,7,8) |
| bnd-syn-0014-6113ae | A |  | root | y | host_root, tmp_scratch | mount/injected, mount/baked, mount/injected, mount/baked | 2 (2,1,8) | 7 (7,7,6) |
| bnd-syn-0015-369ada | C |  | non_root | y | docker_socket, kube_sa_token, run_secrets_ro | plaintext/baked, ref/baked, plaintext/injected | 8 (8,8,8) | 8 (8,9,8) |
| bnd-syn-0016-5a2d93 | A |  | non_root | y | data_ro, docker_socket | mount/injected | 6 (6,6,6) | 7 (8,7,7) |
| bnd-syn-0017-9e7c8b | C |  | non_root |  | data_ro, data_rw | none | 3 (8,3,3) | 7 (7,9,7) |
| bnd-syn-0018-a8a3bb | B |  | non_root |  | none | mount/injected, ref/injected, plaintext/injected | 9 (9,8,10) | 9 (8,9,9) |
| bnd-syn-0019-7135a7 | A |  | non_root |  | data_ro, docker_socket, host_etc | ref/baked, ref/injected, mount/injected, plaintext/injected | 7 (8,5,7) | 8 (8,8,7) |

## containment

Scored by both teachers: 12. INSUFFICIENT_EVIDENCE: 8. Failed: 0.

- Teacher agreement: mean |median difference| 2.67; exact agreement on 0/12; within 1 on 2/12.
- Within-teacher spread across samples (max - min): mean 1.54.
- Median score histogram (both teachers pooled): 0:2 3:2 5:1 6:8 7:4 8:6 9:1

| bundle | ctx | gw | user | privileged | mounts | creds (class/prov) | qwen2.5:7b | mistral-nemo |
|---|---|---|---|---|---|---|---|---|
| bnd-syn-0000-978906 | C |  | non_root | y | data_rw | none | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0001-71b35c | A |  | non_root |  | kube_sa_token, run_secrets_ro | none | 7 (8,7,6) | 9 (6,9,9) |
| bnd-syn-0002-e58dcb | C | y | root |  | data_rw, host_etc, host_root | ref/injected | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0003-58db79 | C |  | non_root | y | docker_socket, kube_sa_token | plaintext/injected, ref/injected, ref/injected, plaintext/baked | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0004-506300 | A |  | root |  | data_rw, docker_socket | plaintext/injected, ref/injected, mount/injected, ref/injected | 3 (3,3,3) | 6 (7,6,6) |
| bnd-syn-0005-3cb433 | D |  | non_root |  | none | plaintext/baked, mount/baked | 7 (7,7,6) | 8 (7,8,8) |
| bnd-syn-0006-313416 | A |  | non_root |  | data_ro, tmp_scratch | none | 6 (7,6,6) | 7 (7,7,8) |
| bnd-syn-0007-9ae1ac | E | y | root |  | host_root | mount/baked, plaintext/injected | 6 (6,7,5) | 8 (8,8,9) |
| bnd-syn-0008-a92416 | E |  | non_root | y | data_rw | plaintext/baked, ref/baked, ref/baked, plaintext/baked | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0009-8c8243 | A |  | root | y | none | mount/injected | 0 (0,0,0) | 6 (6,5,7) |
| bnd-syn-0010-2774bd | E | y | non_root |  | none | ref/injected | 6 (6,6,6) | 8 (7,8,9) |
| bnd-syn-0011-090b0b | D |  | non_root |  | host_root | ref/baked, mount/injected, ref/injected, plaintext/injected | 6 (6,6,6) | 8 (6,8,8) |
| bnd-syn-0012-f8fc76 | D |  | root |  | run_secrets_ro | ref/injected, plaintext/injected, ref/injected, plaintext/injected | 6 (6,6,7) | 8 (8,9,7) |
| bnd-syn-0013-8a8fde | D |  | root | y | docker_socket, host_root | plaintext/baked, plaintext/baked, plaintext/injected | 0 (3,0,0) | 5 (6,3,5) |
| bnd-syn-0014-6113ae | A |  | root | y | host_root, tmp_scratch | mount/injected, mount/baked, mount/injected, mount/baked | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0015-369ada | C |  | non_root | y | docker_socket, kube_sa_token, run_secrets_ro | plaintext/baked, ref/baked, plaintext/injected | 3 (6,3,2) | 7 (7,5,7) |
| bnd-syn-0016-5a2d93 | A |  | non_root | y | data_ro, docker_socket | mount/injected | INSUFF (permissions) | INSUFF (permissions) |
| bnd-syn-0017-9e7c8b | C |  | non_root |  | data_ro, data_rw | none | 6 (6,8,6) | 8 (8,8,7) |
| bnd-syn-0018-a8a3bb | B |  | non_root |  | none | mount/injected, ref/injected, plaintext/injected | INSUFF (permissions, mounts) | INSUFF (permissions, mounts) |
| bnd-syn-0019-7135a7 | A |  | non_root |  | data_ro, docker_socket, host_etc | ref/baked, ref/injected, mount/injected, plaintext/injected | INSUFF (permissions) | INSUFF (permissions) |

The scenario columns are the generator's facts, shown here for review only; the labellers never saw them. Where a bundle hid a fact (a BLIND or PARTIAL attribute), the labeller could not see it either.
