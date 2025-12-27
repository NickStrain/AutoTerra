"""
Terraform Sandbox Testing Service
Validates and tests Terraform code in isolated environments
"""

import os
import subprocess
import tempfile
import shutil
import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class ValidationResult:
    """Result of terraform validation"""
    valid: bool
    format_valid: bool
    init_success: bool
    validate_output: str
    errors: List[str]
    warnings: List[str]


@dataclass
class SecurityScanResult:
    """Result of security scanning"""
    passed: bool
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    findings: List[Dict]
    scanner: str


@dataclass
class TestResult:
    """Complete test result"""
    status: str
    timestamp: str
    validation: Optional[ValidationResult]
    security_scans: List[SecurityScanResult]
    plan_output: Optional[str]
    overall_passed: bool
    summary: str


class TerraformSandboxTester:
    """Tests Terraform code in isolated sandbox"""
    
    def __init__(self):
        self.resource_pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"')
        self.provider_pattern = re.compile(r'provider\s+"([^"]+)"')
    
    def create_sandbox(self) -> str:
        """Create temporary sandbox directory"""
        sandbox_dir = tempfile.mkdtemp(prefix="terraform_test_")
        print(f"Created sandbox: {sandbox_dir}")
        return sandbox_dir
    
    def cleanup_sandbox(self, sandbox_dir: str):
        """Clean up sandbox directory"""
        try:
            shutil.rmtree(sandbox_dir)
            print(f"Cleaned up sandbox: {sandbox_dir}")
        except Exception as e:
            print(f"ERROR: Failed to cleanup: {e}")
    
    def write_terraform_file(self, sandbox_dir: str, content: str):
        """Write Terraform file to sandbox"""
        filepath = os.path.join(sandbox_dir, 'main.tf')
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Written main.tf to sandbox")
    
    def run_command(self, sandbox_dir: str, command: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        """Run command in sandbox"""
        try:
            result = subprocess.run(
                command,
                cwd=sandbox_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    def validate_terraform(self, sandbox_dir: str) -> ValidationResult:
        """Validate Terraform code"""
        print("\nValidating Terraform code...")
        errors = []
        warnings = []
        
        # Check format
        print("  Checking format...")
        fmt_code, _, fmt_err = self.run_command(sandbox_dir, ['terraform', 'fmt', '-check'])
        format_valid = fmt_code == 0
        if not format_valid:
            warnings.append("Code is not properly formatted")
        
        # Initialize
        print("  Running terraform init...")
        init_code, init_out, init_err = self.run_command(
            sandbox_dir, ['terraform', 'init', '-no-color']
        )
        init_success = init_code == 0
        
        if not init_success:
            errors.append(f"Terraform init failed: {init_err}")
            return ValidationResult(
                valid=False,
                format_valid=format_valid,
                init_success=False,
                validate_output=init_err,
                errors=errors,
                warnings=warnings
            )
        
        # Validate
        print("  Running terraform validate...")
        val_code, val_out, val_err = self.run_command(
            sandbox_dir, ['terraform', 'validate', '-json']
        )
        
        validate_output = val_out + val_err
        
        try:
            if val_out:
                val_result = json.loads(val_out)
                valid = val_result.get('valid', False)
                
                if 'diagnostics' in val_result:
                    for diag in val_result['diagnostics']:
                        severity = diag.get('severity', 'error')
                        msg = f"{diag.get('summary', '')}: {diag.get('detail', '')}"
                        
                        if severity == 'error':
                            errors.append(msg)
                        else:
                            warnings.append(msg)
            else:
                valid = val_code == 0
                if not valid:
                    errors.append(val_err if val_err else "Validation failed")
        except:
            valid = val_code == 0
            if not valid:
                errors.append(val_err)
        
        print(f"  Validation: {'PASSED' if valid else 'FAILED'}")
        
        return ValidationResult(
            valid=valid,
            format_valid=format_valid,
            init_success=init_success,
            validate_output=validate_output,
            errors=errors,
            warnings=warnings
        )
    
    def scan_with_tfsec(self, sandbox_dir: str) -> Optional[SecurityScanResult]:
        """Scan with tfsec"""
        print("\nRunning tfsec security scan...")
        
        # Check if tfsec is installed
        check_code, _, _ = self.run_command(sandbox_dir, ['which', 'tfsec'])
        if check_code != 0:
            print("  WARNING: tfsec not installed, skipping security scan")
            return None
        
        code, stdout, stderr = self.run_command(
            sandbox_dir, ['tfsec', '.', '--format', 'json', '--no-color']
        )
        
        if code != 0 and not stdout:
            print(f"  WARNING: tfsec failed: {stderr}")
            return None
        
        try:
            result = json.loads(stdout) if stdout else {'results': []}
            findings = result.get('results', [])
            
            severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
            for finding in findings:
                severity = finding.get('severity', 'UNKNOWN')
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            passed = severity_counts['CRITICAL'] == 0 and severity_counts['HIGH'] == 0
            
            print(f"  Found {len(findings)} issues")
            print(f"  Critical: {severity_counts['CRITICAL']}, High: {severity_counts['HIGH']}, " +
                  f"Medium: {severity_counts['MEDIUM']}, Low: {severity_counts['LOW']}")
            
            return SecurityScanResult(
                passed=passed,
                critical_issues=severity_counts['CRITICAL'],
                high_issues=severity_counts['HIGH'],
                medium_issues=severity_counts['MEDIUM'],
                low_issues=severity_counts['LOW'],
                findings=findings[:10],  # Limit to first 10 findings
                scanner='tfsec'
            )
        except Exception as e:
            print(f"  ERROR: Failed to parse tfsec output: {e}")
            return None
    
    def scan_with_checkov(self, sandbox_dir: str) -> Optional[SecurityScanResult]:
        """Scan with checkov"""
        print("\nRunning checkov security scan...")
        
        # Check if checkov is installed
        check_code, _, _ = self.run_command(sandbox_dir, ['which', 'checkov'])
        if check_code != 0:
            print("  WARNING: checkov not installed, skipping security scan")
            return None
        
        code, stdout, stderr = self.run_command(
            sandbox_dir, ['checkov', '-d', '.', '--output', 'json', '--quiet'], timeout=120
        )
        
        try:
            result = json.loads(stdout) if stdout else {}
            summary = result.get('summary', {})
            
            failed = summary.get('failed', 0)
            passed_checks = summary.get('passed', 0)
            
            passed = failed == 0
            
            print(f"  Passed: {passed_checks}, Failed: {failed}")
            
            # Get detailed findings
            findings = []
            for check_result in result.get('results', {}).get('failed_checks', [])[:10]:
                findings.append({
                    'check_id': check_result.get('check_id', ''),
                    'check_name': check_result.get('check_name', ''),
                    'file_path': check_result.get('file_path', ''),
                    'resource': check_result.get('resource', '')
                })
            
            return SecurityScanResult(
                passed=passed,
                critical_issues=0,
                high_issues=failed,
                medium_issues=0,
                low_issues=0,
                findings=findings,
                scanner='checkov'
            )
        except Exception as e:
            print(f"  WARNING: checkov parsing failed: {e}")
            return None
    
    def generate_plan(self, sandbox_dir: str) -> Optional[str]:
        """Generate Terraform plan"""
        print("\nGenerating Terraform plan...")
        
        plan_code, plan_out, plan_err = self.run_command(
            sandbox_dir, ['terraform', 'plan', '-no-color']
        )
        
        if plan_code == 0:
            print("  Plan generated successfully")
            return plan_out
        else:
            print(f"  Plan generation failed: {plan_err}")
            return plan_err
    
    def test_terraform_code(self, terraform_code: str, 
                           run_security_scan: bool = True,
                           generate_plan: bool = True) -> TestResult:
        """Test Terraform code with all checks"""
        print("="*70)
        print("TERRAFORM SANDBOX TESTING")
        print("="*70)
        
        sandbox_dir = self.create_sandbox()
        
        try:
            # Write Terraform code
            self.write_terraform_file(sandbox_dir, terraform_code)
            
            # Validation
            validation = self.validate_terraform(sandbox_dir)
            
            # Security scanning
            security_scans = []
            if run_security_scan and validation.valid:
                tfsec_result = self.scan_with_tfsec(sandbox_dir)
                if tfsec_result:
                    security_scans.append(tfsec_result)
                
                checkov_result = self.scan_with_checkov(sandbox_dir)
                if checkov_result:
                    security_scans.append(checkov_result)
            
            # Generate plan
            plan_output = None
            if generate_plan and validation.valid:
                plan_output = self.generate_plan(sandbox_dir)
            
            # Determine overall result
            overall_passed = validation.valid
            if security_scans:
                overall_passed &= all(scan.passed for scan in security_scans)
            
            # Generate summary
            summary = self._generate_summary(validation, security_scans, overall_passed)
            
            status = "success" if overall_passed else "failed"
            
            return TestResult(
                status=status,
                timestamp=datetime.now().isoformat(),
                validation=validation,
                security_scans=security_scans,
                plan_output=plan_output,
                overall_passed=overall_passed,
                summary=summary
            )
        
        except Exception as e:
            print(f"ERROR: Test failed: {e}")
            return TestResult(
                status="error",
                timestamp=datetime.now().isoformat(),
                validation=None,
                security_scans=[],
                plan_output=None,
                overall_passed=False,
                summary=f"Test error: {str(e)}"
            )
        
        finally:
            self.cleanup_sandbox(sandbox_dir)
    
    def _generate_summary(self, validation: ValidationResult, 
                         security_scans: List[SecurityScanResult],
                         overall_passed: bool) -> str:
        """Generate test summary"""
        summary = []
        summary.append("TEST SUMMARY")
        summary.append("-" * 40)
        
        # Validation
        summary.append(f"Validation: {'PASSED' if validation.valid else 'FAILED'}")
        if validation.errors:
            summary.append(f"  Errors: {len(validation.errors)}")
            for error in validation.errors[:3]:
                summary.append(f"    - {error}")
        if validation.warnings:
            summary.append(f"  Warnings: {len(validation.warnings)}")
        
        # Security
        if security_scans:
            summary.append(f"\nSecurity Scans: {len(security_scans)}")
            for scan in security_scans:
                summary.append(f"  {scan.scanner}: {'PASSED' if scan.passed else 'FAILED'}")
                if not scan.passed:
                    summary.append(f"    Critical: {scan.critical_issues}, High: {scan.high_issues}")
        
        summary.append(f"\nOVERALL: {'PASSED' if overall_passed else 'FAILED'}")
        
        return '\n'.join(summary)
    
    def to_dict(self, result: TestResult) -> Dict:
        """Convert result to dictionary"""
        return {
            'status': result.status,
            'timestamp': result.timestamp,
            'validation': asdict(result.validation) if result.validation else None,
            'security_scans': [asdict(scan) for scan in result.security_scans],
            'plan_output': result.plan_output,
            'overall_passed': result.overall_passed,
            'summary': result.summary
        }


# Example usage
if __name__ == "__main__":
    tester = TerraformSandboxTester()
    
    # Example Terraform code
    terraform_code = """
terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-west-2"
}

resource "aws_s3_bucket" "example" {
  bucket = "my-test-bucket-12345"
  
  tags = {
    Name        = "My bucket"
    Environment = "Dev"
  }
}

resource "aws_s3_bucket_versioning" "example" {
  bucket = aws_s3_bucket.example.id
  
  versioning_configuration {
    status = "Enabled"
  }
}
"""
    
    result = tester.test_terraform_code(
        terraform_code=terraform_code,
        run_security_scan=True,
        generate_plan=True
    )
    
    print("\n" + result.summary)
    print(f"\nTest result: {result.status}")
    print(f"Overall passed: {result.overall_passed}")