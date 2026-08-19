# Benchmark Results

This document records the measurements collected while executing the steps described in
[Benchmark Execution](benchmark_execution.md).

# <Platform Name>

## Environment

Tests are performed on with the following parameters:

* CPU description: <CPU description>
* CPU cores: <CPU cores>
* CPU frequency: <CPU frequency>
* RAM: <RAM size>
* Storage: <Storage description>
* etc.

## Operational Speed

### Install new deployable items

Timing (seconds):

| Items / Metric |  Total | Download | Install | Prepare | Network |  Start  |
|:--------------:|:------:|:--------:|:-------:|:-------:|:-------:|:-------:|
| 1              |        |          |         |         |         |         |
| 8              |        |          |         |         |         |         |
| 16             |        |          |         |         |         |         |

### Install cached deployable items

Timing (seconds):

| Items / Metric |  Total | Download | Install | Prepare | Network |  Start  |
|:--------------:|:------:|:--------:|:-------:|:-------:|:-------:|:-------:|
| 1              |        |          |         |         |         |         |
| 8              |        |          |         |         |         |         |
| 16             |        |          |         |         |         |         |

### Start/stop already installed instances

Start timing (seconds):

| Instances / Metric | Start total | Start network | Start instances |
|:------------------:|:-----------:|:-------------:|:---------------:|
| 1                  |             |               |                 |
| 8                  |             |               |                 |
| 16                 |             |               |                 |
| 64                 |             |               |                 |
| 128                |             |               |                 |
| 256                |             |               |                 |

Stop timing (seconds):

| Instances / Metric | Stop total | Stop network | Stop instances |
|:------------------:|:----------:|:------------:|:--------------:|
| 1                  |            |              |                |
| 8                  |            |              |                |
| 16                 |            |              |                |
| 64                 |            |              |                |
| 128                |            |              |                |
| 256                |            |              |                |

## Container disk I/O

### Encrypted storage

Sequential throughput (MB/s):

| Instances | Write throughput | Read throughput |
|:---------:|:----------------:|:---------------:|
|     1     |                  |                 |
|     8     |                  |                 |
|    16     |                  |                 |
|    64     |                  |                 |

Sequential latency (ms):

| Instances | Write avg | Write p99 | Read avg | Read p99 |
|:---------:|:---------:|:---------:|:--------:|:--------:|
|     1     |           |           |          |          |
|     8     |           |           |          |          |
|    16     |           |           |          |          |
|    64     |           |           |          |          |

Random IOPS:

| Instances | Write IOPS | Read IOPS |
|:---------:|:----------:|:---------:|
|     1     |            |           |
|     8     |            |           |
|    16     |            |           |
|    64     |            |           |

Random latency (ms):

| Instances | Write avg | Write p99 | Read avg | Read p99 |
|:---------:|:---------:|:---------:|:--------:|:--------:|
|     1     |           |           |          |          |
|     8     |           |           |          |          |
|    16     |           |           |          |          |
|    64     |           |           |          |          |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

### Unencrypted storage

Sequential throughput (MB/s):

| Instances | Write throughput | Read throughput |
|:---------:|:----------------:|:---------------:|
|     1     |                  |                 |
|     8     |                  |                 |
|    16     |                  |                 |
|    64     |                  |                 |

Sequential latency (ms):

| Instances | Write avg | Write p99 | Read avg | Read p99 |
|:---------:|:---------:|:---------:|:--------:|:--------:|
|     1     |           |           |          |          |
|     8     |           |           |          |          |
|    16     |           |           |          |          |
|    64     |           |           |          |          |

Random IOPS:

| Instances | Write IOPS | Read IOPS |
|:---------:|:----------:|:---------:|
|     1     |            |           |
|     8     |            |           |
|    16     |            |           |
|    64     |            |           |

Random latency (ms):

| Instances | Write avg | Write p99 | Read avg | Read p99 |
|:---------:|:---------:|:---------:|:--------:|:--------:|
|     1     |           |           |          |          |
|     8     |           |           |          |          |
|    16     |           |           |          |          |
|    64     |           |           |          |          |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

## Network

### Bandwidth

#### Service to service

TCP throughput (Mbps):

| Instances | TCP Uplink | TCP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP throughput (Mbps):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP loss (%):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP jitter (ms):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

#### Service to unit

TCP throughput (Mbps):

| Instances | TCP Uplink | TCP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP throughput (Mbps):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP loss (%):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP jitter (ms):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

#### Service to external host

TCP throughput (Mbps):

| Instances | TCP Uplink | TCP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP throughput (Mbps):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP loss (%):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

UDP jitter (ms):

| Instances | UDP Uplink | UDP Downlink |
|:---------:|:----------:|:------------:|
|     1     |            |              |
|     8     |            |              |
|    16     |            |              |
|    64     |            |              |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

### Latency

#### Service to service

TCP RTT (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

UDP RTT (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

#### Service to unit

TCP RTT (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

UDP RTT (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

#### Service to external host

TCP RTT (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

UDP RTT (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

System CPU (%, whole-host max during the run):

| Instances | System CPU |
|:---------:|:----------:|
|     1     |            |
|     8     |            |
|    16     |            |
|    64     |            |

### DNS

#### Service to service

Resolve time (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

#### Service to unit

Resolve time (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

#### Service to external host

Resolve time (µs):

| Instances | p50 | p99 | p999 |
|:---------:|:---:|:---:|:----:|
|     1     |     |     |      |
|     8     |     |     |      |
|    16     |     |     |      |
|    64     |     |     |      |

## CPU / RAM used by AosCore

### Install new deployable items

CPU (%):

| Items / Component  |   CM    |   SM    |   IAM   |
|:------------------:|:-------:|:-------:|:-------:|
| 0                  |         |         |         |
| 1                  |         |         |         |
| 8                  |         |         |         |
| 16                 |         |         |         |

RAM (PSS, MiB):

| Items / Component  |   CM    |   SM    |   IAM   |
|:------------------:|:-------:|:-------:|:-------:|
| 0                  |         |         |         |
| 1                  |         |         |         |
| 8                  |         |         |         |
| 16                 |         |         |         |

### Install cached deployable items

CPU (%):

| Items / Component  |   CM    |   SM    |   IAM   |
|:------------------:|:-------:|:-------:|:-------:|
| 0                  |         |         |         |
| 1                  |         |         |         |
| 8                  |         |         |         |
| 16                 |         |         |         |

RAM (PSS, MiB):

| Items / Component  |   CM    |   SM    |   IAM   |
|:------------------:|:-------:|:-------:|:-------:|
| 0                  |         |         |         |
| 1                  |         |         |         |
| 8                  |         |         |         |
| 16                 |         |         |         |

### Start/stop already installed instances

CPU (%):

| Instances / Component  |   CM    |   SM    |   IAM   |
|:----------------------:|:-------:|:-------:|:-------:|
| 0                      |         |         |         |
| 1                      |         |         |         |
| 8                      |         |         |         |
| 16                     |         |         |         |
| 64                     |         |         |         |
| 128                    |         |         |         |
| 256                    |         |         |         |

RAM (PSS, MiB):

| Instances / Component  |   CM    |   SM    |   IAM   |
|:----------------------:|:-------:|:-------:|:-------:|
| 0                      |         |         |         |
| 1                      |         |         |         |
| 8                      |         |         |         |
| 16                     |         |         |         |
| 64                     |         |         |         |
| 128                    |         |         |         |
| 256                    |         |         |         |
