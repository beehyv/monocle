import unittest
import logging
from io import StringIO
from monocle_apptrace.exporters.log_exporter import LogExporter

class TestLogExporter(unittest.TestCase):

    def setUp(self):
        self.log_stream = StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        self.log_exporter = LogExporter(log_to_console=False, log_level=logging.DEBUG)
        self.log_exporter.logger.addHandler(self.log_handler)

    def tearDown(self):
        self.log_exporter.logger.removeHandler(self.log_handler)

    def test_export_info_log(self):
        self.log_exporter.export_log("This is an INFO message.", level='info')
        self.log_handler.flush()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("INFO", log_output)
        self.assertIn("This is an INFO message.", log_output)

    def test_export_debug_log(self):
        self.log_exporter.export_log("This is a DEBUG message.", level='debug')
        self.log_handler.flush()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("DEBUG", log_output)
        self.assertIn("This is a DEBUG message.", log_output)

    def test_export_error_log(self):
        self.log_exporter.export_log("This is an ERROR message.", level='error')
        self.log_handler.flush()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("ERROR", log_output)
        self.assertIn("This is an ERROR message.", log_output)

    def test_dump_to_logger(self):
        external_logger_name = "external_logger"
        external_logger = self.log_exporter.dump_to_logger(external_logger_name, log_level=logging.INFO)
        external_logger.info("This is a log from external logger")

        self.assertIn("INFO", self.log_stream.getvalue())
        self.assertIn("This is a log from external logger", self.log_stream.getvalue())

    def test_no_duplicate_handlers(self):
        external_logger_name = "external_logger"
        external_logger = self.log_exporter.dump_to_logger(external_logger_name)

        initial_handler_count = len(external_logger.handlers)
        self.log_exporter.dump_to_logger(external_logger_name)
        final_handler_count = len(external_logger.handlers)

        self.assertEqual(initial_handler_count, final_handler_count)


if __name__ == '__main__':
    unittest.main()
