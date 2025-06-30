"""
Ivy Build Mode Mixin for PANTHER-Ivy

This mixin provides build mode management functionality that can be applied
in Docker containers to control compilation flags and Z3 build configuration.
"""

import os
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging


class IvyBuildModeMixin:
    """
    Mixin for managing Ivy build modes in containerized environments.
    # For local development, this mixin allows setting and retrieving
    
    Provides three build modes while preserving original Shadow compatibility:
    - '' (empty): Original method - no extra flags (preserves Shadow compatibility)
    - 'debug-asan': Debug build with AddressSanitizer and debugging symbols
    - 'rel-lto': Release build with Link Time Optimization
    - 'release-static-pgo': Release build with PGO, static linking, and native optimization
    """
    
    # Build mode configurations
    BUILD_MODE_CONFIGS = {
        '': {
            'description': 'Original method (Shadow compatible)',
            'cpp_flags': '',
            'cmake_args': []
        },
        'debug-asan': {
            'description': 'Debug with AddressSanitizer',
            'cpp_flags': '-O1 -g -fsanitize=address -fno-omit-frame-pointer -D_GLIBCXX_DEBUG',
            'cmake_args': [
                '-DCMAKE_BUILD_TYPE=Debug',
                '-DBUILD_LIBZ3_SHARED=OFF',
                '-DSANITIZE_ADDRESS=ON'
            ]
        },
        'rel-lto': {
            'description': 'Release with Link Time Optimization',
            'cpp_flags': '-O3 -flto -fuse-linker-plugin -g',
            'cmake_args': [
                '-DCMAKE_BUILD_TYPE=Release',
                '-DLINK_TIME_OPTIMIZATION=ON',
                '-DBUILD_LIBZ3_SHARED=OFF'
            ]
        },
        'release-static-pgo': {
            'description': 'Release with PGO and static linking',
            'cpp_flags': '-O3 -flto -fuse-linker-plugin -fprofile-use -march=native -static -s',
            'cmake_args': [
                '-DCMAKE_BUILD_TYPE=Release',
                '-DLINK_TIME_OPTIMIZATION=ON',
                '-DBUILD_LIBZ3_SHARED=OFF',
                '-DCMAKE_C_FLAGS=-fprofile-use',
                '-DCMAKE_CXX_FLAGS=-fprofile-use',
                '-DCMAKE_POSITION_INDEPENDENT_CODE=OFF'
            ]
        }
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._build_mode = None
        self._z3_build_path = None
    
    def get_build_mode(self) -> str:
        """Get the current build mode from environment or config"""
        if self._build_mode is None:
            # Try environment variable first
            self._build_mode = os.getenv('BUILD_MODE', '')
            
            # Try service_config_to_test.plugin_config (primary location for build_mode)
            if (hasattr(self, 'service_config_to_test') and 
                hasattr(self.service_config_to_test, 'plugin_config') and
                isinstance(self.service_config_to_test.plugin_config, dict) and
                'build_mode' in self.service_config_to_test.plugin_config):
                config_build_mode = self.service_config_to_test.plugin_config['build_mode']
                if config_build_mode:  # Only use if not empty
                    self._build_mode = config_build_mode
            
            # Try service_config_to_test.implementation (fallback for direct YAML config)
            elif (hasattr(self, 'service_config_to_test') and 
                hasattr(self.service_config_to_test, 'implementation') and
                hasattr(self.service_config_to_test.implementation, 'build_mode')):
                config_build_mode = getattr(self.service_config_to_test.implementation, 'build_mode', '')
                if config_build_mode:  # Only use if not empty
                    self._build_mode = config_build_mode
            
            # Try direct service_config_to_test for backward compatibility
            elif hasattr(self, 'service_config_to_test') and hasattr(self.service_config_to_test, 'build_mode'):
                config_build_mode = getattr(self.service_config_to_test, 'build_mode', '')
                if config_build_mode:  # Only use if not empty
                    self._build_mode = config_build_mode
            
            # Try legacy config access for backward compatibility
            elif hasattr(self, 'config') and hasattr(self.config, 'build_mode'):
                self._build_mode = getattr(self.config, 'build_mode', '')
        
        return self._build_mode or ''  # Ensure we always return a string
    
    def set_build_mode(self, mode: str) -> None:
        """Set the build mode and validate it"""
        if mode not in self.BUILD_MODE_CONFIGS:
            valid_modes = list(self.BUILD_MODE_CONFIGS.keys())
            raise ValueError(f"Invalid BUILD_MODE='{mode}'. Valid modes: {valid_modes}")
        
        self._build_mode = mode
        os.environ['BUILD_MODE'] = mode
        self.logger.info(f"Set build mode to: {mode} ({self.BUILD_MODE_CONFIGS[mode]['description']})")
    
    def get_cpp_build_flags(self) -> str:
        """Get C++ compilation flags for current build mode"""
        mode = self.get_build_mode()
        return self.BUILD_MODE_CONFIGS[mode]['cpp_flags']
    
    def get_z3_cmake_args(self) -> List[str]:
        """Get CMake arguments for Z3 build in current mode"""
        mode = self.get_build_mode()
        return self.BUILD_MODE_CONFIGS[mode]['cmake_args'].copy()
    
    def should_use_cmake_for_z3(self) -> bool:
        """Determine if CMake should be used for Z3 build"""
        mode = self.get_build_mode()
        return bool(mode)  # Use CMake for non-empty modes, mk_make.py for empty/original
    
    def prepare_build_environment(self) -> Dict[str, str]:
        """Prepare environment variables for build process"""
        env = os.environ.copy()
        mode = self.get_build_mode()
        
        # Set BUILD_MODE for child processes
        env['BUILD_MODE'] = mode
        
        # Add mode-specific environment variables if needed
        if mode == 'debug-asan':
            env['ASAN_OPTIONS'] = 'detect_leaks=1:abort_on_error=1'
        elif mode == 'release-static-pgo':
            env['CFLAGS'] = env.get('CFLAGS', '') + ' -fprofile-use'
            env['CXXFLAGS'] = env.get('CXXFLAGS', '') + ' -fprofile-use'
        
        return env
    
    def build_z3_with_mode(self, project_root: str = None) -> bool:
        """Build Z3 using the appropriate method for current build mode"""
        try:
            if project_root is None:
                project_root = os.getcwd()
            
            mode = self.get_build_mode()
            z3_dir = os.path.join(project_root, 'submodules', 'z3')
            
            if not os.path.exists(z3_dir):
                self.logger.error("Z3 submodule not found. Run 'git submodule update --init --recursive'")
                return False
            
            self.logger.info(f"Building Z3 with mode: {mode}")
            
            if self.should_use_cmake_for_z3():
                return self._build_z3_cmake(z3_dir, project_root)
            else:
                return self._build_z3_legacy(z3_dir, project_root)
                
        except Exception as e:
            self.logger.error(f"Failed to build Z3: {e}")
            return False
    
    def _build_z3_cmake(self, z3_dir: str, project_root: str) -> bool:
        """Build Z3 using CMake"""
        mode = self.get_build_mode()
        build_dir = os.path.join(z3_dir, 'build', mode)
        
        # Create build directory
        Path(build_dir).mkdir(parents=True, exist_ok=True)
        
        # Prepare CMake command
        cmake_args = self.get_z3_cmake_args()
        cmake_cmd = [
            'cmake', '-S', z3_dir, '-B', build_dir,
            f'-DCMAKE_INSTALL_PREFIX={project_root}'
        ] + cmake_args
        
        # Configure
        self.logger.info(f"Configuring Z3 with CMake: {' '.join(cmake_cmd)}")
        result = subprocess.run(cmake_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.logger.error(f"CMake configure failed: {result.stderr}")
            return False
        
        # Build
        build_cmd = ['cmake', '--build', build_dir, '--parallel', '4']
        self.logger.info(f"Building Z3: {' '.join(build_cmd)}")
        result = subprocess.run(build_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.logger.error(f"Z3 build failed: {result.stderr}")
            return False
        
        # Copy library to expected location
        self._copy_z3_library(build_dir, project_root)
        return True
    
    def _build_z3_legacy(self, z3_dir: str, project_root: str) -> bool:
        """Build Z3 using legacy mk_make.py method"""
        original_cwd = os.getcwd()
        
        try:
            os.chdir(z3_dir)
            ivy_dir = os.path.join(project_root, 'ivy')
            
            # Prepare mk_make.py command
            if platform.system() != 'Windows':
                cmd = ['python3', 'scripts/mk_make.py', '--python', 
                       '--prefix', project_root, '--pypkgdir', f'{ivy_dir}/']
            else:
                cmd = ['python3', 'scripts/mk_make.py', '-x', '--python', 
                       '--pypkgdir', f'{ivy_dir}/']
            
            # Run mk_make.py
            self.logger.info(f"Running mk_make.py: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"mk_make.py failed: {result.stderr}")
                return False
            
            # Build
            os.chdir('build')
            
            if platform.system() == 'Windows':
                # Windows build with Visual Studio
                build_cmd = ['nmake']
            else:
                # Unix build with make
                build_cmd = ['make', '-j', '4']
            
            self.logger.info(f"Building Z3: {' '.join(build_cmd)}")
            result = subprocess.run(build_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"Z3 build failed: {result.stderr}")
                return False
            
            # Install (Unix only)
            if platform.system() != 'Windows':
                install_cmd = ['make', 'install']
                result = subprocess.run(install_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    self.logger.warning(f"Z3 install failed: {result.stderr}")
            
            return True
            
        finally:
            os.chdir(original_cwd)
    
    def _copy_z3_library(self, build_dir: str, project_root: str) -> None:
        """Copy Z3 library to expected location"""
        import shutil
        
        # Determine library name based on platform
        if platform.system() == 'Windows':
            lib_name = 'z3.lib'
        else:
            lib_name = 'libz3.a'
        
        src_path = os.path.join(build_dir, lib_name)
        dst_dir = os.path.join(project_root, 'ivy', 'lib')
        dst_path = os.path.join(dst_dir, lib_name)
        
        # Create destination directory
        Path(dst_dir).mkdir(parents=True, exist_ok=True)
        
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            self.logger.info(f"Copied {src_path} to {dst_path}")
        else:
            self.logger.warning(f"Z3 library not found at {src_path}")
    
    def validate_build_environment(self) -> bool:
        """Validate that the build environment is properly configured"""
        mode = self.get_build_mode()
        
        # Check if mode is valid
        if mode not in self.BUILD_MODE_CONFIGS:
            self.logger.error(f"Invalid build mode: {mode}")
            return False
        
        # Check for required tools
        required_tools = ['cmake', 'make'] if platform.system() != 'Windows' else ['cmake']
        
        for tool in required_tools:
            if not self._check_tool_available(tool):
                self.logger.error(f"Required tool not found: {tool}")
                return False
        
        return True
    
    def _check_tool_available(self, tool: str) -> bool:
        """Check if a build tool is available"""
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def get_build_summary(self) -> Dict[str, Union[str, bool]]:
        """Get a summary of current build configuration"""
        mode = self.get_build_mode()
        config = self.BUILD_MODE_CONFIGS[mode]
        
        return {
            'build_mode': mode,
            'description': config['description'],
            'cpp_flags': config['cpp_flags'],
            'use_cmake': self.should_use_cmake_for_z3(),
            'environment_valid': self.validate_build_environment()
        }