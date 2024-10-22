import logging

class LogExporter:
    def __init__(self, log_to_console=True, log_to_file=None, log_level=logging.INFO):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        if log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(self.formatter)
            self.logger.addHandler(console_handler)

        if log_to_file:
            file_handler = logging.FileHandler(log_to_file)
            file_handler.setFormatter(self.formatter)
            self.logger.addHandler(file_handler)

    def export_log(self, message, level='info'):
        if level.lower() == 'debug':
            self.logger.debug(message)
        elif level.lower() == 'warning':
            self.logger.warning(message)
        elif level.lower() == 'error':
            self.logger.error(message)
        elif level.lower() == 'critical':
            self.logger.critical(message)
        else:
            self.logger.info(message)

    def dump_to_logger(self, logger_name, log_level=logging.INFO, add_handlers=True):
        external_logger = logging.getLogger(logger_name)
        external_logger.setLevel(log_level)

        if add_handlers:
            for handler in self.logger.handlers:
                if handler not in external_logger.handlers:
                    external_logger.addHandler(handler)

        for handler in external_logger.handlers:
            if handler.formatter is None:
                handler.setFormatter(self.formatter)

        return external_logger
