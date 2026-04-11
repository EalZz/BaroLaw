| Case ID          | Expected                         | In Corpus   | BM25 Rank   | Vector Rank   | Fused Rank   | Final Rank   | Root Cause     |
|:-----------------|:---------------------------------|:------------|:------------|:--------------|:-------------|:-------------|:---------------|
| FRAUD_12_S       | 형법 제347조                     | ✔           | ✘           | ✘             | ✘            | ✘            | Retrieval Fail |
| REAL_ESTATE_02_S | 경범죄 처벌법                    | ✔           | ✘           | 66            | ✘            | ✘            | Retrieval Fail |
| REAL_ESTATE_24_M | 집합건물법                       | ✘           | ✘           | ✘             | ✘            | ✘            | Retrieval Fail |
| TRAFFIC_01_S     | 특정범죄 가중처벌 등에 관한 법률 | ✔           | 23          | 13            | 25           | 25           | Scoring Issue  |
| TRAFFIC_02_S     | 도로교통법 제156조               | ✔           | 23          | 41            | 46           | ✘            | Rerank Fail    |
| TRAFFIC_09_S     | 도로교통법                       | ✔           | 12          | 10            | 13           | 13           | Scoring Issue  |
| TRAFFIC_15_S     | 도로교통법                       | ✔           | 2           | 37            | 4            | 4            | Scoring Issue  |