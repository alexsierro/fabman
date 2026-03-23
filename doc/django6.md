# Upgrade Django from 4.2 to 6

## Update Postgresql
Update PSQL 12 to 16 in docker compose

### From old version (12) ###
* Dump DB *
docker exec fabman-db-1 pg_dumpall -U postgres > dump.sql

* Remove old data volume *
docker rm fabman-db-1 fabman-db-1
docker volume rm fabman_postgres_data fabman_postgres_data

### From new version (16)
* Restore dump *
docker exec -i fabman-db-1 psql -U hello_django postgres < dump.sql

* Reset the password for hello_django user *
ALTER USER hello_django WITH PASSWORD 'hello_django';


TODO: Collectstatic is not yet working automatically

