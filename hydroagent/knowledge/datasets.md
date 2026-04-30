---
keywords: [数据集, dataset, camels, caravan, hydrodataset, 流域, basin, 数据路径]
---

# 支持的水文数据集

HydroAgent 通过 [hydrodataset](https://github.com/OuyangWenyu/hydrodataset) 包访问水文数据集。
hydrodataset 以 [AquaFetch](https://github.com/hyex-research/AquaFetch) 为后端，首次访问时自动下载原始数据并缓存为 NetCDF 格式，后续读取直接从本地缓存加载。

---

## 路径配置（必须）

hydrodataset 从用户主目录的 `~/hydro_setting.yml` 读取数据路径，与 HydroAgent 的 `configs/private.py` 中的 `DATASET_DIR` 是**独立的两套配置**。

`~/hydro_setting.yml` 示例（Windows）：

```yaml
local_data_path:
  root: 'D:\data'
  datasets-origin: 'D:\data'        # 各数据集子目录的公共父目录
  cache: 'D:\data\cache'
```

- `datasets-origin`：所有数据集的公共父目录，AquaFetch 会在其中找 `CAMELS_US/`、`CAMELS_GB/` 等子目录
- `cache`：NetCDF 缓存目录，首次读取时自动生成

**HydroAgent 会根据 `configs/private.py` 中的 `DATASET_DIR` 自动生成此文件，无需手动编辑。**

`DATASET_DIR` 应指向**具体数据集目录**（如 `D:\data\CAMELS_US`），HydroAgent 自动取其父目录（`D:\data`）写入 `datasets-origin`：

```
DATASET_DIR = D:\data              <- 填父目录（不是 CAMELS_US 本身）
                 |
                 v
datasets-origin = D:\data          <- AquaFetch 自动在此找 CAMELS_US/ 子目录
datasets-interim = D:\data         <- hydromodel 也需要此字段，默认同 datasets-origin
```

> AquaFetch 会自动在 `datasets-origin` 下拼接数据集类名（如 `CAMELS_US`），
> 因此 `DATASET_DIR` 必须是数据集文件夹的**父目录**，而不是数据集目录本身。

> 如果没有 `~/hydro_setting.yml`，hydrodataset 会回落到 `~/hydrodataset_data/` 作为默认路径。

---

## 首次下载说明

首次对某数据集调用任何读取函数时，AquaFetch 会自动下载并解压原始数据。下载时间取决于数据集大小和网络条件：

| 规模 | 示例 | 大致时间 |
|------|------|---------|
| 小型 (< 1 GB) | CAMELS-CL, CAMELS-SE | 10~30 分钟 |
| 中型 (1~5 GB) | CAMELS-AUS, CAMELS-BR | 30 分钟~1 小时 |
| 大型 (10~20 GB) | CAMELS-US, LamaH-CE | 1~3 小时 |
| 超大型 (> 30 GB) | HYSETS, Caravan | 3~6 小时以上 |

建议在有条件时提前手动下载数据集。

---

## 支持的数据集列表

在 `configs/model_config.py` 中设置 `DEFAULT_DATA_SOURCE` 为下面表格中的 **data_source_type** 字符串。

| data_source_type | 数据集名称 | 地区 | 流域数 | 时间跨度 | 大小 |
|------------------|-----------|------|--------|---------|------|
| `camels_us` | CAMELS-US | 美国 | 671 | 1980-2014 | 14.6 GB |
| `camels_gb` | CAMELS-GB | 英国 | 671 | 1970-2015 | 244 MB |
| `camels_br` | CAMELS-BR | 巴西 | 897 | 1980-2024 | 1.4 GB |
| `camels_aus` | CAMELS-AUS | 澳大利亚 | 561 | 1950-2022 | 2.1 GB |
| `camels_cl` | CAMELS-CL | 智利 | 516 | 1913-2018 | 208 MB |
| `camels_de` | CAMELS-DE | 德国 | 1582 | 1951-2020 | 2.2 GB |
| `camels_dk` | CAMELS-DK | 丹麦 | 304 | 1989-2023 | 1.4 GB |
| `camels_ch` | CAMELS-CH | 瑞士 | 331 | 1981-2020 | 793 MB |
| `camels_fr` | CAMELS-FR | 法国 | 654 | 1970-2021 | 364 MB |
| `camels_se` | CAMELS-SE | 瑞典 | 50 | 1961-2020 | 16 MB |
| `camels_fi` | CAMELS-FI | 芬兰 | 320 | 1961-2023 | 382 MB |
| `camels_ind` | CAMELS-IND | 印度 | 472 | 1980-2020 | 529 MB |
| `camels_col` | CAMELS-COL | 哥伦比亚 | 347 | 1981-2022 | 81 MB |
| `camels_nz` | CAMELS-NZ | 新西兰 | 369 | 1972-2024 | 4.8 GB |
| `camels_lux` | CAMELS-LUX | 卢森堡 | 56 | 2004-2021 | 1.4 GB |
| `camels_es` | BULL (西班牙) | 西班牙 | 484 | 1951-2021 | 2.2 GB |
| `camelsh_kr` | CAMELSH-KR | 韩国 | 178 | 2000-2019 | 3.1 GB |
| `camelsh` | CAMELSH | 美国（小时） | 9008 | 1980-2024 | ~10 GB |
| `caravan` | Caravan | 全球 | 16299 | 1950-2023 | 24.8 GB |
| `grdc_caravan` | GRDC-Caravan | 全球 | 5357 | 1950-2023 | 16.4 GB |
| `lamah_ce` | LamaH-CE | 中欧 | 859 | 1981-2019 | 16.3 GB |
| `lamah_ice` | LamaH-Ice | 冰岛 | 111 | 1950-2021 | 9.6 GB |
| `hysets` | HYSETS | 北美 | 14425 | 1950-2023 | 41.9 GB |
| `estreams` | EStreams | 欧洲 | 17130 | 1950-2023 | 12.3 GB |

---

## 切换数据集示例

```python
# configs/model_config.py
DEFAULT_DATA_SOURCE = "camels_gb"   # 切换到 CAMELS-GB（英国）
DEFAULT_TRAIN_PERIOD = ["1990-10-01", "2008-09-30"]
DEFAULT_TEST_PERIOD  = ["2008-10-01", "2015-09-30"]
```

```
You> 率定GR4J模型，流域39001，CAMELS-GB数据集
```

---

## 注意事项

- 不同数据集的流域 ID 格式不同：CAMELS-US 为 8 位数字，CAMELS-GB/AUS 等为字母数字混合
- HydroAgent 的 `validate_basin` 工具会自动识别当前数据集并做对应的 ID 验证
- 各数据集支持的变量（如降水、蒸发、径流字段名）已由 hydrodataset 统一标准化
- 本文档中列出的数据集均可通过 AquaFetch 自动下载，无需手动处理原始数据格式
