-- 自动生成：云端 ods_zbzx DDL（副本→1）。Doris 2.1。
-- 由 _doris_ddl_sync.py 生成，勿手改；重跑覆盖。

CREATE DATABASE IF NOT EXISTS `ods_zbzx`;
USE `ods_zbzx`;

DROP TABLE IF EXISTS `ods_company_basic_info`;
CREATE TABLE `ods_company_basic_info` (
  `company_id` bigint NOT NULL COMMENT "公司ID(对应 aodeta_data.company.id)",
  `reg_number` text NULL COMMENT "工商注册号",
  `business_scope` text NULL COMMENT "经营范围",
  `approved_time` datetime NULL COMMENT "核准日期",
  `company_name` text NULL COMMENT "企业名称",
  `company_enname` text NULL COMMENT "企业英文名称",
  `usc_code` text NULL COMMENT "统一社会信用代码",
  `former_name` text NULL COMMENT "曾用名",
  `to_time` datetime NULL COMMENT "经营期限至",
  `estiblish_time` datetime NULL COMMENT "注册日期",
  `legal_person_name` text NULL COMMENT "法定代表人",
  `business_address` text NULL COMMENT "经营场所(年报通信地址)",
  `company_org_type` text NULL COMMENT "企业类型",
  `category_code` text NULL COMMENT "国民经济行业代码",
  `category_name` text NULL COMMENT "国民经济行业名称",
  `province` text NULL COMMENT "省份",
  `org_number` text NULL COMMENT "组织机构代码",
  `pension_count` text NULL COMMENT "参保人数(源为 text)",
  `reg_capital` text NULL COMMENT "注册资本",
  `actual_capital` text NULL COMMENT "实收注册资金",
  `reg_capital_num` decimal(20,6) NULL COMMENT "注册资金数值(万元)",
  `reg_capital_type` text NULL COMMENT "注册资金币种",
  `telephone` text NULL COMMENT "注册电话",
  `email` text NULL COMMENT "注册邮箱",
  `from_time` datetime NULL COMMENT "经营期限自",
  `reg_location` text NULL COMMENT "注册地址",
  `region_code` text NULL COMMENT "行政区划代码",
  `reg_institute` text NULL COMMENT "注册机关",
  `stock_realcapital` decimal(20,6) NULL COMMENT "股东实缴额合计(SUM)",
  `tax_number` text NULL COMMENT "纳税人识别号",
  `create_time` datetime NULL COMMENT "记录创建时间",
  `update_time` datetime NULL COMMENT "记录更新时间"
) ENGINE=OLAP
UNIQUE KEY(`company_id`)
COMMENT 'ODS层-公司基本信息'
DISTRIBUTED BY HASH(`company_id`) BUCKETS 48
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_financial_info_attachment_cn`;
CREATE TABLE `ods_financial_info_attachment_cn` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-金融信息附件表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_financial_info_attachment_global`;
CREATE TABLE `ods_financial_info_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-金融信息附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_financial_info_cn`;
CREATE TABLE `ods_financial_info_cn` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `impact` varchar(100) NULL COMMENT "影响方面（正面/负面）",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-金融信息主表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_financial_info_global`;
CREATE TABLE `ods_financial_info_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `impact` varchar(100) NULL COMMENT "影响方面（正面/负面）",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-金融信息主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_industry_report_attachment_cn`;
CREATE TABLE `ods_industry_report_attachment_cn` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-产业报告附件表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_industry_report_attachment_global`;
CREATE TABLE `ods_industry_report_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-产业报告附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_industry_report_cn`;
CREATE TABLE `ods_industry_report_cn` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `publishing_organization` text NULL COMMENT "发布机构",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-产业报告主表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_industry_report_global`;
CREATE TABLE `ods_industry_report_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `publishing_organization` text NULL COMMENT "发布机构",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-产业报告主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_international_news`;
CREATE TABLE `ods_international_news` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime(6) NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime(6) NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime(6) NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `process_status` smallint NULL DEFAULT "0" COMMENT "处理状态 (0:待处理, 1:已清洗)",
  `event_time_flag` smallint NOT NULL DEFAULT "1" COMMENT "时间类型标识 (1:事件时间, 0:创建时间)",
  `quality_score` decimal(5,2) NULL COMMENT "数据质量评分",
  `source_url_hash` char(32) NULL COMMENT "URL的MD5，用于入库前的快速去重",
  `etl_version` varchar(20) NULL COMMENT "ETL清洗版本",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `impact` varchar(100) NULL COMMENT "影响方面（正面/负面）",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `minio_path_text` text NULL COMMENT "Minio清洗后纯文本路径",
  `title` text NULL COMMENT "标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT '国际资讯主表'
AUTO PARTITION BY RANGE (date_trunc(`event_time`, 'month'))
(PARTITION p20210601000000 VALUES [('2021-06-01 00:00:00'), ('2021-07-01 00:00:00')),
PARTITION p20240501000000 VALUES [('2024-05-01 00:00:00'), ('2024-06-01 00:00:00')),
PARTITION p20240601000000 VALUES [('2024-06-01 00:00:00'), ('2024-07-01 00:00:00')),
PARTITION p20240701000000 VALUES [('2024-07-01 00:00:00'), ('2024-08-01 00:00:00')),
PARTITION p20240801000000 VALUES [('2024-08-01 00:00:00'), ('2024-09-01 00:00:00')),
PARTITION p20240901000000 VALUES [('2024-09-01 00:00:00'), ('2024-10-01 00:00:00')),
PARTITION p20241001000000 VALUES [('2024-10-01 00:00:00'), ('2024-11-01 00:00:00')),
PARTITION p20241101000000 VALUES [('2024-11-01 00:00:00'), ('2024-12-01 00:00:00')),
PARTITION p20241201000000 VALUES [('2024-12-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p20250601000000 VALUES [('2025-06-01 00:00:00'), ('2025-07-01 00:00:00')),
PARTITION p20250701000000 VALUES [('2025-07-01 00:00:00'), ('2025-08-01 00:00:00')),
PARTITION p20250801000000 VALUES [('2025-08-01 00:00:00'), ('2025-09-01 00:00:00')),
PARTITION p20250901000000 VALUES [('2025-09-01 00:00:00'), ('2025-10-01 00:00:00')),
PARTITION p20251201000000 VALUES [('2025-12-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p20260101000000 VALUES [('2026-01-01 00:00:00'), ('2026-02-01 00:00:00')),
PARTITION p20260301000000 VALUES [('2026-03-01 00:00:00'), ('2026-04-01 00:00:00')),
PARTITION p20260401000000 VALUES [('2026-04-01 00:00:00'), ('2026-05-01 00:00:00')),
PARTITION p20260501000000 VALUES [('2026-05-01 00:00:00'), ('2026-06-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 10
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"compression" = "ZSTD",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_international_news_attachment`;
CREATE TABLE `ods_international_news_attachment` (
  `id` bigint NOT NULL COMMENT "唯一标识 ID",
  `event_time` datetime(6) NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime(6) NULL DEFAULT CURRENT_TIMESTAMP COMMENT "数据入库时间",
  `update_time` datetime(6) NULL COMMENT "数据更新时间",
  `original_table` varchar(255) NULL COMMENT "原始数据来源表名",
  `raw_content` text NULL COMMENT "原始全文内容/HTML 源码",
  `clean_content` text NULL COMMENT "清洗后的纯文本内容",
  `other_content` text NULL COMMENT "备用内容字段 1",
  `other_content2` text NULL COMMENT "备用内容字段 2"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT '国际资讯附加内容表'
AUTO PARTITION BY RANGE (date_trunc(`event_time`, 'month'))
(PARTITION p20250601000000 VALUES [('2025-06-01 00:00:00'), ('2025-07-01 00:00:00')),
PARTITION p20250701000000 VALUES [('2025-07-01 00:00:00'), ('2025-08-01 00:00:00')),
PARTITION p20250801000000 VALUES [('2025-08-01 00:00:00'), ('2025-09-01 00:00:00')),
PARTITION p20250901000000 VALUES [('2025-09-01 00:00:00'), ('2025-10-01 00:00:00')),
PARTITION p20251201000000 VALUES [('2025-12-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p20260101000000 VALUES [('2026-01-01 00:00:00'), ('2026-02-01 00:00:00')),
PARTITION p20260301000000 VALUES [('2026-03-01 00:00:00'), ('2026-04-01 00:00:00')),
PARTITION p20260401000000 VALUES [('2026-04-01 00:00:00'), ('2026-05-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 10
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"compression" = "ZSTD",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_international_news_attachment_global`;
CREATE TABLE `ods_international_news_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-国际时事附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_international_news_global`;
CREATE TABLE `ods_international_news_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `impact` varchar(100) NULL COMMENT "影响方面（正面/负面）",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-国际时事主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_invention_patent_attachment_cn`;
CREATE TABLE `ods_invention_patent_attachment_cn` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-发明专利附件表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_invention_patent_attachment_global`;
CREATE TABLE `ods_invention_patent_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-发明专利附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_invention_patent_cn`;
CREATE TABLE `ods_invention_patent_cn` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `filing_date` datetime NULL COMMENT "申请日期",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `is_authorized` smallint NULL COMMENT "是否授权（1授权，0未授权）",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `legal_status` varchar(200) NULL COMMENT "专利法律状态",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "专利标题",
  `applicant` text NULL COMMENT "申请人",
  `ipc_type` text NULL COMMENT "专利分类号",
  `affiliation` text NULL COMMENT "申请人所属机构",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-发明专利主表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_invention_patent_global`;
CREATE TABLE `ods_invention_patent_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `filing_date` datetime NULL COMMENT "申请日期",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `is_authorized` smallint NULL COMMENT "是否授权（1授权，0未授权）",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `legal_status` varchar(200) NULL COMMENT "专利法律状态",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "专利标题",
  `applicant` text NULL COMMENT "申请人",
  `ipc_type` text NULL COMMENT "专利分类号",
  `affiliation` text NULL COMMENT "申请人所属机构",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-发明专利主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_item_category`;
CREATE TABLE `ods_item_category` (
  `level1_code` varchar(8) NULL COMMENT "1级编码",
  `level1_name` varchar(64) NULL COMMENT "1级名称",
  `level2_code` varchar(16) NULL COMMENT "2级编码",
  `level2_name` varchar(128) NULL COMMENT "2级名称",
  `level3_code` varchar(16) NULL COMMENT "3级编码",
  `level3_name` varchar(255) NULL COMMENT "3级名称",
  `level4_code` varchar(32) NULL COMMENT "4级编码",
  `level4_name` varchar(255) NULL COMMENT "4级名称",
  `level5_code` varchar(32) NULL COMMENT "5级编码",
  `level5_name` varchar(255) NULL COMMENT "5级名称",
  `source_sheet` varchar(64) NULL COMMENT "数据来源(原xlsx的sheet名)",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "记录创建时间"
) ENGINE=OLAP
DUPLICATE KEY(`level1_code`)
COMMENT '产品品类原始表(政府采购货物名录+补充医疗器械)'
DISTRIBUTED BY HASH(`level1_code`) BUCKETS 4
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728"
);;

DROP TABLE IF EXISTS `ods_key_events_attachment_cn`;
CREATE TABLE `ods_key_events_attachment_cn` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-重点事件附件表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_key_events_attachment_global`;
CREATE TABLE `ods_key_events_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-重点事件附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_key_events_cn`;
CREATE TABLE `ods_key_events_cn` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-重点事件主表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_key_events_global`;
CREATE TABLE `ods_key_events_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-重点事件主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_market_analysis_attachment_cn`;
CREATE TABLE `ods_market_analysis_attachment_cn` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-市场分析附件表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_market_analysis_attachment_global`;
CREATE TABLE `ods_market_analysis_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-市场分析附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_market_analysis_cn`;
CREATE TABLE `ods_market_analysis_cn` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `purchaser` varchar(500) NULL COMMENT "采购单位",
  `region` varchar(500) NULL COMMENT "所属区域",
  `announcement_type` varchar(255) NULL COMMENT "公告类型",
  `amount` varchar(255) NULL COMMENT "标的金额",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "公共标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-市场分析主表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_market_analysis_global`;
CREATE TABLE `ods_market_analysis_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `purchaser` varchar(500) NULL COMMENT "采购单位",
  `region` varchar(500) NULL COMMENT "所属区域",
  `announcement_type` varchar(255) NULL COMMENT "公告类型",
  `amount` varchar(255) NULL COMMENT "标的金额",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "公共标题",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-市场分析主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_oversea_company_info`;
CREATE TABLE `ods_oversea_company_info` (
  `id` varchar(64) NOT NULL COMMENT "主键，MD5(query_name+full_name+address)",
  `query_company_name` varchar(500) NULL COMMENT "查询企业名称",
  `company_full_name` varchar(1000) NULL COMMENT "企业全名",
  `company_short_name` varchar(500) NULL COMMENT "企业简称",
  `country` varchar(200) NULL COMMENT "国家（中文+英文）",
  `city` varchar(500) NULL COMMENT "城市（中文+英文）",
  `address` varchar(2000) NULL COMMENT "详细地址",
  `owner_founder` varchar(1000) NULL COMMENT "所有人/创始人",
  `main_business` text NULL COMMENT "主营业务",
  `contact_person` varchar(500) NULL COMMENT "联系人",
  `email` varchar(500) NULL COMMENT "联系邮箱",
  `twitter` varchar(500) NULL COMMENT "Twitter账号",
  `linkedin` varchar(500) NULL COMMENT "LinkedIn账号",
  `phone` varchar(500) NULL COMMENT "联系电话",
  `source_url` varchar(2000) NULL COMMENT "索引链接",
  `create_time` datetime NULL COMMENT "入库时间",
  `update_time` datetime NULL COMMENT "更新时间"
) ENGINE=OLAP
UNIQUE KEY(`id`)
COMMENT 'ODS层-海外企业（买家）原始信息表'
DISTRIBUTED BY HASH(`id`) BUCKETS 16
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_science_literature`;
CREATE TABLE `ods_science_literature` (
  `id` bigint NOT NULL COMMENT "唯一标识 ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "数据入库时间",
  `update_time` datetime NULL COMMENT "数据更新时间",
  `collect_source_id` int NULL COMMENT "采集源 ID",
  `task_id` int NULL COMMENT "采集任务 ID",
  `original_id` int NULL COMMENT "原始数据 ID",
  `collect_source_name` varchar(255) NULL COMMENT "采集来源名称",
  `industry` varchar(255) NULL COMMENT "所属行业/领域分类",
  `original_table` varchar(255) NULL COMMENT "原始数据来源表名",
  `url` varchar(1000) NULL COMMENT "来源原文 URL",
  `minio_path_file` text NULL COMMENT "原始附件在 MinIO 的存储路径",
  `minio_path_raw` text NULL COMMENT "原始 HTML/报文存储路径",
  `title` text NULL COMMENT "文献标题",
  `authors` text NULL COMMENT "作者列表",
  `keyword` text NULL COMMENT "关键词",
  `abstract` text NULL COMMENT "摘要内容",
  `features` json NULL COMMENT "扩展属性（JSON 格式存储）"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS 层-论文文献主表'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_science_literature_attachment`;
CREATE TABLE `ods_science_literature_attachment` (
  `id` bigint NOT NULL COMMENT "关联主表 ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "数据入库时间",
  `update_time` datetime NULL COMMENT "数据更新时间",
  `original_table` varchar(255) NULL COMMENT "来源表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后的正文内容",
  `other_content` text NULL COMMENT "备用内容字段 1",
  `other_content2` text NULL COMMENT "备用内容字段 2",
  `original_id` int NULL COMMENT "原始数据 ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS 层-论文文献附件表'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_science_literature_attachment_global`;
CREATE TABLE `ods_science_literature_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-科技文献附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_science_literature_global`;
CREATE TABLE `ods_science_literature_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "标题",
  `authors` text NULL COMMENT "作者",
  `keyword` text NULL COMMENT "关键词",
  `abstract` text NULL COMMENT "摘要",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-科技文献主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_strategic_policy_attachment_cn`;
CREATE TABLE `ods_strategic_policy_attachment_cn` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-战略政策附件表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_strategic_policy_attachment_global`;
CREATE TABLE `ods_strategic_policy_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-战略政策附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_strategic_policy_cn`;
CREATE TABLE `ods_strategic_policy_cn` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "政策标题",
  `policy_source` text NULL COMMENT "政策来源机构",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-战略政策主表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_strategic_policy_global`;
CREATE TABLE `ods_strategic_policy_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `title` text NULL COMMENT "政策标题",
  `policy_source` text NULL COMMENT "政策来源机构",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-战略政策主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_talent_info_attachment_cn`;
CREATE TABLE `ods_talent_info_attachment_cn` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-人才信息附件表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_talent_info_attachment_global`;
CREATE TABLE `ods_talent_info_attachment_global` (
  `id` bigint NOT NULL COMMENT "关联主表ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `raw_content` text NULL COMMENT "原始全文内容",
  `clean_content` text NULL COMMENT "清洗后正文内容",
  `other_content` text NULL COMMENT "备用内容字段1",
  `other_content2` text NULL COMMENT "备用内容字段2",
  `original_id` int NULL COMMENT "原始数据ID"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-人才信息附件表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_talent_info_cn`;
CREATE TABLE `ods_talent_info_cn` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `full_name` varchar(255) NULL COMMENT "人名",
  `education` varchar(255) NULL COMMENT "学历",
  `job_title` varchar(255) NULL COMMENT "职称",
  `employer` varchar(255) NULL COMMENT "工作单位",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-人才信息主表(国内)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;

DROP TABLE IF EXISTS `ods_talent_info_global`;
CREATE TABLE `ods_talent_info_global` (
  `id` bigint NOT NULL COMMENT "主键ID",
  `event_time` datetime NOT NULL COMMENT "事件时间（分区键）",
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT "创建时间",
  `update_time` datetime NULL COMMENT "更新时间",
  `collect_source_id` int NULL COMMENT "采集源id",
  `task_id` int NULL COMMENT "任务id",
  `original_id` int NULL COMMENT "原表id",
  `collect_source_name` varchar(255) NULL COMMENT "采集源名称",
  `industry` varchar(255) NULL COMMENT "所属行业",
  `original_table` varchar(255) NULL COMMENT "原始表名",
  `full_name` varchar(255) NULL COMMENT "人名",
  `education` varchar(255) NULL COMMENT "学历",
  `job_title` varchar(255) NULL COMMENT "职称",
  `employer` varchar(255) NULL COMMENT "工作单位",
  `url` varchar(1000) NULL COMMENT "原始采集网页地址",
  `minio_path_file` text NULL COMMENT "Minio文件存储路径",
  `minio_path_raw` text NULL COMMENT "Minio原文HTML路径",
  `features` json NULL COMMENT "其余内容 (JSON格式)"
) ENGINE=OLAP
UNIQUE KEY(`id`, `event_time`)
COMMENT 'ODS层-人才信息主表(国外)'
PARTITION BY RANGE(`event_time`)
(PARTITION p2016 VALUES [('2016-01-01 00:00:00'), ('2017-01-01 00:00:00')),
PARTITION p2017 VALUES [('2017-01-01 00:00:00'), ('2018-01-01 00:00:00')),
PARTITION p2018 VALUES [('2018-01-01 00:00:00'), ('2019-01-01 00:00:00')),
PARTITION p2019 VALUES [('2019-01-01 00:00:00'), ('2020-01-01 00:00:00')),
PARTITION p2020 VALUES [('2020-01-01 00:00:00'), ('2021-01-01 00:00:00')),
PARTITION p2021 VALUES [('2021-01-01 00:00:00'), ('2022-01-01 00:00:00')),
PARTITION p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00')),
PARTITION p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00')),
PARTITION p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00')),
PARTITION p2025 VALUES [('2025-01-01 00:00:00'), ('2026-01-01 00:00:00')),
PARTITION p2026 VALUES [('2026-01-01 00:00:00'), ('2027-01-01 00:00:00')),
PARTITION p2027 VALUES [('2027-01-01 00:00:00'), ('2028-01-01 00:00:00')),
PARTITION p2028 VALUES [('2028-01-01 00:00:00'), ('2029-01-01 00:00:00')))
DISTRIBUTED BY HASH(`id`) BUCKETS 32
PROPERTIES (
"replication_allocation" = "tag.location.default: 1",
"min_load_replica_num" = "-1",
"is_being_synced" = "false",
"dynamic_partition.enable" = "true",
"dynamic_partition.time_unit" = "YEAR",
"dynamic_partition.time_zone" = "Asia/Shanghai",
"dynamic_partition.start" = "-10",
"dynamic_partition.end" = "2",
"dynamic_partition.prefix" = "p",
"dynamic_partition.replication_allocation" = "tag.location.default: 1",
"dynamic_partition.buckets" = "32",
"dynamic_partition.create_history_partition" = "true",
"dynamic_partition.history_partition_num" = "-1",
"dynamic_partition.hot_partition_num" = "0",
"dynamic_partition.reserved_history_periods" = "NULL",
"dynamic_partition.storage_policy" = "",
"storage_medium" = "hdd",
"storage_format" = "V2",
"inverted_index_storage_format" = "V1",
"enable_unique_key_merge_on_write" = "true",
"light_schema_change" = "true",
"disable_auto_compaction" = "false",
"enable_single_replica_compaction" = "false",
"group_commit_interval_ms" = "10000",
"group_commit_data_bytes" = "134217728",
"enable_mow_light_delete" = "false"
);;
