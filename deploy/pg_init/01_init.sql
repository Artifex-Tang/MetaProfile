-- 初始化脚本：在 metaprofile 用户下创建集成测试专用数据库
-- 由 postgres docker-entrypoint-initdb.d 自动执行（仅首次启动）

\c postgres

CREATE DATABASE test_metaprofile
    OWNER metaprofile
    ENCODING 'UTF8'
    LC_COLLATE 'en_US.utf8'
    LC_CTYPE 'en_US.utf8'
    TEMPLATE template0;

GRANT ALL PRIVILEGES ON DATABASE test_metaprofile TO metaprofile;
