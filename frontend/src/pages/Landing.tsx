import { ArrowRight, Code, Shield, Zap, Terminal, DollarSign, TestTube, Layers, CheckCircle, LogIn, LogOut, CreditCard, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';

const Landing = () => {
  const { user, signOut } = useAuth();
  const { subscribed, loading: subLoading, createCheckout } = useSubscription();

  const handleSubscribe = async () => {
    try {
      await createCheckout();
    } catch (error) {
      console.error('Error creating checkout:', error);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-6 h-6 text-primary" />
            <span className="text-xl font-bold tracking-tight">autoterra</span>
          </div>
          <div className="flex items-center gap-3">
            {user ? (
              <>
                {subscribed ? (
                  <Link to="/app" className="btn-primary text-sm">
                    Launch App
                  </Link>
                ) : (
                  <button
                    onClick={handleSubscribe}
                    disabled={subLoading}
                    className="btn-primary text-sm flex items-center gap-2"
                  >
                    {subLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <CreditCard className="w-4 h-4" />
                    )}
                    Subscribe $9.99/mo
                  </button>
                )}
                <button
                  onClick={() => signOut()}
                  className="btn-secondary text-sm flex items-center gap-2"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </>
            ) : (
              <Link to="/auth" className="btn-primary text-sm flex items-center gap-2">
                <LogIn className="w-4 h-4" />
                Sign In
              </Link>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 mb-6 rounded-full border border-border/50 bg-muted/30 text-sm text-muted-foreground">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            AI-Powered Infrastructure
          </div>
          
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
            <span className="text-gradient">Production-ready</span>
            <br />
            Terraform in seconds
          </h1>
          
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
            Generate secure, tested, and cost-optimized Terraform code that integrates seamlessly with your existing infrastructure.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            {user ? (
              subscribed ? (
                <Link 
                  to="/app" 
                  className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4"
                >
                  Start Generating
                  <ArrowRight className="w-5 h-5" />
                </Link>
              ) : (
                <button
                  onClick={handleSubscribe}
                  disabled={subLoading}
                  className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4"
                >
                  {subLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <CreditCard className="w-5 h-5" />
                  )}
                  Subscribe to Get Started - $9.99/mo
                </button>
              )
            ) : (
              <Link 
                to="/auth" 
                className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4"
              >
                Sign In to Get Started
                <ArrowRight className="w-5 h-5" />
              </Link>
            )}
            <a 
              href="https://github.com" 
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-8 py-4 border border-border rounded-lg text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
            >
              View on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* Key Capabilities */}
      <section className="py-16 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="grid md:grid-cols-4 gap-4 text-center">
            {[
              { icon: CheckCircle, label: 'Production Ready' },
              { icon: Shield, label: 'Security Validated' },
              { icon: TestTube, label: 'Auto Tested' },
              { icon: DollarSign, label: 'Cost Predicted' },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center justify-center gap-2 py-3 px-4 rounded-lg border border-border/30 bg-muted/10">
                <Icon className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Code Preview */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="card-minimal overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50 bg-muted/20">
              <div className="w-3 h-3 rounded-full bg-red-500/60" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
              <div className="w-3 h-3 rounded-full bg-green-500/60" />
              <span className="ml-4 text-xs text-muted-foreground font-mono">main.tf</span>
            </div>
            <pre className="p-6 overflow-x-auto text-sm">
              <code className="font-mono text-primary/90">
{`resource "aws_s3_bucket" "data_prod" {
  bucket = "data-prod"
  
  tags = {
    Name        = "data-prod"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "data_prod" {
  bucket = aws_s3_bucket.data_prod.id
  versioning_configuration {
    status = "Enabled"
  }
}`}
              </code>
            </pre>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6 border-t border-border/30">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            Enterprise-Grade Generation
          </h2>
          <p className="text-center text-muted-foreground mb-16 max-w-2xl mx-auto">
            AutoTerra doesn't just generate code — it validates, tests, and optimizes for your specific environment.
          </p>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="card-minimal p-6">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <Zap className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Instant Generation</h3>
              <p className="text-sm text-muted-foreground">
                Describe infrastructure in plain English. Get production-ready Terraform code in seconds.
              </p>
            </div>
            
            <div className="card-minimal p-6">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <Layers className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Infrastructure Aware</h3>
              <p className="text-sm text-muted-foreground">
                Analyzes your existing infrastructure to generate compatible, non-conflicting resources.
              </p>
            </div>
            
            <div className="card-minimal p-6">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <Shield className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Security First</h3>
              <p className="text-sm text-muted-foreground">
                Built-in security validation ensures compliance with CIS benchmarks and best practices.
              </p>
            </div>
            
            <div className="card-minimal p-6">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <TestTube className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Auto Testing</h3>
              <p className="text-sm text-muted-foreground">
                Validates syntax, runs plan checks, and tests against your state before you apply.
              </p>
            </div>
            
            <div className="card-minimal p-6">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <DollarSign className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Cost Prediction</h3>
              <p className="text-sm text-muted-foreground">
                Estimates monthly costs before deployment. Get insights on resource pricing and optimization.
              </p>
            </div>
            
            <div className="card-minimal p-6">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <Code className="w-5 h-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Clean Output</h3>
              <p className="text-sm text-muted-foreground">
                Properly formatted, documented code following HashiCorp's style conventions.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 px-6 border-t border-border/30">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-16">
            How It Works
          </h2>
          
          <div className="space-y-8">
            {[
              { step: '01', title: 'Describe', desc: 'Tell AutoTerra what infrastructure you need in plain English.' },
              { step: '02', title: 'Analyze', desc: 'AI analyzes requirements, checks existing infrastructure, and plans resources.' },
              { step: '03', title: 'Generate', desc: 'Production-ready Terraform code is generated with security and cost validation.' },
              { step: '04', title: 'Deploy', desc: 'Download, review, and apply — confident your code is tested and optimized.' },
            ].map(({ step, title, desc }) => (
              <div key={step} className="flex items-start gap-6">
                <span className="text-4xl font-bold text-primary/20">{step}</span>
                <div>
                  <h3 className="text-xl font-semibold mb-1">{title}</h3>
                  <p className="text-muted-foreground">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 border-t border-border/30">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready to automate your infrastructure?
          </h2>
          <p className="text-muted-foreground mb-8">
            Stop writing boilerplate. Start deploying faster.
          </p>
          {user ? (
            subscribed ? (
              <Link 
                to="/app" 
                className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4"
              >
                Get Started
                <ArrowRight className="w-5 h-5" />
              </Link>
            ) : (
              <button
                onClick={handleSubscribe}
                disabled={subLoading}
                className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4"
              >
                {subLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <CreditCard className="w-5 h-5" />
                )}
                Subscribe Now - $9.99/mo
              </button>
            )
          ) : (
            <Link 
              to="/auth" 
              className="btn-primary inline-flex items-center gap-2 text-lg px-8 py-4"
            >
              Get Started
              <ArrowRight className="w-5 h-5" />
            </Link>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-border/30">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-primary" />
            <span>autoterra</span>
          </div>
          <span>Built with AI</span>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
