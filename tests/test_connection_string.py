import unittest
from unittest.mock import MagicMock, patch
from urllib import parse

from tap_mongodb import (
    get_connection_string,
    normalize_connection_string,
    require_database,
    validate_connection_config,
)


class TestConnectionString(unittest.TestCase):
    def setUp(self):
        self.config = {
            "host": "dummy-host",
            "user": "dummy-user",
            "password": "dummy-password",
            "auth_database": "dummy-auth-database",
            "database": "dummy-databse",
            "port": "2017"
        }

    def test_minimal_config(self):
        expected_default_string = "mongodb://dummy-user:dummy-password@dummy-host:2017/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database"
        expected_srv_string = "mongodb+srv://dummy-user:dummy-password@dummy-host/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database"

        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_default_string, connection_string)

        self.config["srv"] = "true"
        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_srv_string, connection_string)


    def test_replica_set_config(self):
        self.config["replica_set"] = "dummy-replica-set"

        expected_default_string = "mongodb://dummy-user:dummy-password@dummy-host:2017/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database&replicaSet=dummy-replica-set"
        expected_srv_string = "mongodb+srv://dummy-user:dummy-password@dummy-host/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database&replicaSet=dummy-replica-set"

        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_default_string, connection_string)

        self.config["srv"] = "true"
        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_srv_string, connection_string)


    def test_strict_ssl_config(self):
        self.config["ssl"] = "true"

        expected_default_string = "mongodb://dummy-user:dummy-password@dummy-host:2017/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database&tls=true"
        expected_srv_string = "mongodb+srv://dummy-user:dummy-password@dummy-host/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database&tls=true"

        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_default_string, connection_string)

        self.config["srv"] = "true"
        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_srv_string, connection_string)


    def test_weak_ssl_config(self):
        self.config["ssl"] = "true"
        self.config["verify_mode"] = "false"

        expected_default_string = "mongodb://dummy-user:dummy-password@dummy-host:2017/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database&tls=true&tlsAllowInvalidCertificates=true"
        expected_srv_string = "mongodb+srv://dummy-user:dummy-password@dummy-host/dummy-databse?readPreference=secondaryPreferred&authSource=dummy-auth-database&tls=true&tlsAllowInvalidCertificates=true"

        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_default_string, connection_string)

        self.config["srv"] = "true"
        connection_string = get_connection_string(self.config)
        self.assertEqual(expected_srv_string, connection_string)

    def test_connection_string_config(self):
        uri = "mongodb://user:pass@host:27017/?authSource=admin&tls=true"
        self.assertEqual(uri, get_connection_string({"connection_string": uri}))

    def test_normalize_connection_string_ssl_aliases(self):
        uri = (
            "mongodb://user:pass@host:27017/"
            "?ssl=true&sslInvalidHostNameAllowed=true&authSource=admin"
        )
        params = dict(parse.parse_qsl(parse.urlparse(normalize_connection_string(uri)).query))
        self.assertEqual(params["tls"], "true")
        self.assertEqual(params["tlsAllowInvalidHostnames"], "true")
        self.assertEqual(params["authSource"], "admin")
        self.assertNotIn("ssl", params)
        self.assertNotIn("sslInvalidHostNameAllowed", params)

    def test_connection_string_config_normalizes_ssl_aliases(self):
        uri = (
            "mongodb://user:pass@host:27017/"
            "?ssl=true&sslInvalidHostNameAllowed=true&authSource=admin"
        )
        params = dict(parse.parse_qsl(
            parse.urlparse(get_connection_string({"connection_string": uri})).query
        ))
        self.assertEqual(params["tls"], "true")
        self.assertEqual(params["tlsAllowInvalidHostnames"], "true")

    def test_normalize_studio_3t_proxy_forces_direct_connection(self):
        uri = (
            "mongodb://user:pass@dw-mongodb-prod.gospringboard.io:27017/"
            "?ssl=true&sslInvalidHostNameAllowed=true"
            "&3t.sniName=springboard-datawarehouse-1-shard-00-00-zu4mc.mongodb.net"
            "&authSource=admin"
        )
        params = dict(parse.parse_qsl(parse.urlparse(normalize_connection_string(uri)).query))
        self.assertEqual(params["tls"], "true")
        self.assertEqual(params["tlsAllowInvalidHostnames"], "true")
        self.assertEqual(params["directConnection"], "true")
        self.assertEqual(params["authSource"], "admin")
        self.assertTrue(all(not key.lower().startswith("3t.") for key in params))

    def test_validate_connection_config_accepts_connection_string(self):
        validate_connection_config({"connection_string": "mongodb://user:pass@host:27017/"})

    def test_validate_connection_config_requires_discrete_params(self):
        with self.assertRaises(Exception) as ctx:
            validate_connection_config({"host": "dummy-host"})
        self.assertIn("missing required keys", str(ctx.exception))

    def test_require_database_passes_when_set(self):
        require_database(MagicMock(), {"database": "mydb"})

    def test_require_database_lists_and_fails_with_connection_string(self):
        client = MagicMock()
        client.list_database_names.return_value = ["admin", "local", "springboard"]

        with self.assertRaises(Exception) as ctx:
            require_database(client, {"connection_string": "mongodb://u:p@h/"})

        self.assertIn("springboard", str(ctx.exception))
        self.assertNotIn("local", str(ctx.exception))

    @patch("tap_mongodb.get_databases")
    def test_require_database_lists_and_fails_with_discrete_params(self, mock_get_databases):
        mock_get_databases.return_value = ["springboard"]
        client = MagicMock()

        with self.assertRaises(Exception) as ctx:
            require_database(client, {
                "auth_database": "admin",
                "user": "hotglue-user",
            })

        self.assertIn("springboard", str(ctx.exception))
        mock_get_databases.assert_called_once_with(client, {
            "auth_database": "admin",
            "user": "hotglue-user",
        })
