from typing import List, Tuple


class IvyOutputPatternMixin:
    """
    Mixin for Ivy-specific output patterns following PANTHER phase-based standard.

    This mixin implements the get_output_patterns() method to organize outputs
    into phase-based directories as discovered in the PANTHER infrastructure.
    """

    def get_output_patterns(self) -> List[Tuple[str, str]]:
        """
        Get phase-based output patterns for Ivy service.

        Returns:
            List[Tuple[str, str]]: Output patterns with phase organization
        """
        patterns = [
            # Phase outputs - following PANTHER standard
            ("pre_compile_stdout", "pre-compile/stdout.log"),
            ("pre_compile_stderr", "pre-compile/stderr.log"),
            ("pre_compile_env", "pre-compile/ivy_env.sh"),

            ("compile_stdout", "compile/stdout.log"),
            ("compile_stderr", "compile/stderr.log"),
            ("compile_status", "compile/compilation_status.txt"),
            ("compile_log", "compile/ivy_compile.log"),

            ("runtime_stdout", "runtime/stdout.log"),
            ("runtime_stderr", "runtime/stderr.log"),
            ("runtime_setup", "runtime/ivy_setup.log"),

            ("test_stdout", "test/stdout.log"),
            ("test_stderr", "test/stderr.log"),
            ("test_results", "test/test_results.json"),

            # Ivy-specific artifacts
            ("ivy_log", "artifacts/ivy_{service_name}.log"),
            ("pcap", "artifacts/{service_name}.pcap"),
            ("sslkeylog", "artifacts/sslkeylogfile.txt"),
            ("post_compile_log", "artifacts/ivy_post_compile.log"),
        ]

        # Protocol-specific additions
        if hasattr(self, 'get_protocol_name'):
            protocol = self.get_protocol_name()
            if protocol == "quic":
                patterns.extend([
                    ("qlog", "artifacts/*.qlog"),
                    ("keys", "artifacts/*keys.log"),
                ])

        return patterns