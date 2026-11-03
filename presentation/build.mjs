import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const workspaceDir = path.dirname(fileURLToPath(import.meta.url));
const runtimeRoot = process.env.PRESENTATION_RUNTIME_ROOT ?? path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime');
process.env.RUNTIME_NODE_MODULES ??= path.join(runtimeRoot, 'dependencies/node/node_modules');
const SKILL_DIR = process.env.PRESENTATIONS_SKILL_DIR ?? path.join(os.homedir(), '.codex/plugins/cache/openai-primary-runtime/presentations/26.1020.11618/skills/presentations');
const RUNTIME_PYTHON = process.env.RUNTIME_PYTHON ?? path.join(runtimeRoot, 'dependencies/python/bin/python3');
const { finalizePresentation, resolvePresentationFont } = await import(path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs'));
const FONT = resolvePresentationFont();
const C = { ink:'#162C3B', muted:'#4B626F', teal:'#007E87', blue:'#DCEEF1', pale:'#F3F7F7', line:'#CBDADD', white:'#FFFFFF', orange:'#C35C20' };
const p = Presentation.create({slideSize:{width:1280,height:720}});
const slides=[];

const S = {
  choose:'https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/choose-tool.html',
  terraform:'https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/terraform.html',
  state:'https://developer.hashicorp.com/terraform/language/state',
  s3:'https://developer.hashicorp.com/terraform/language/backend/s3',
  cfn:'https://docs.aws.amazon.com/prescriptive-guidance/latest/choose-iac-tool/cloudformation.html',
  cfnTemplate:'https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-templates.html',
  cdk:'https://docs.aws.amazon.com/cdk/v2/guide/home.html',
  cdkPrereq:'https://docs.aws.amazon.com/cdk/v2/guide/prerequisites.html',
  cdkBootstrap:'https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html',
  ct:'https://docs.aws.amazon.com/controltower/latest/userguide/what-is-control-tower.html',
  aft:'https://docs.aws.amazon.com/controltower/latest/userguide/aft-overview.html',
  irsa:'https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html',
  rdsIam:'https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html',
};

function text(s, value, x,y,w,h, size=28, color=C.ink, bold=false, align='left') {
  const a=s.shapes.add({geometry:'textbox',name:value.replace(/\n/g,' ').slice(0,75),position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  a.text=value;
  a.text.style={typeface:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'top',autoFit:'none',insets:0};
  return a;
}
function rect(s,x,y,w,h,fill=C.pale,line=C.line){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:line,width:1}});}
function line(s,x,y,w,color=C.line){return rect(s,x,y,w,1,color,color);}
function node(s,label,x,y,w,h,{fill=C.blue,size=25,bold=true}={}){
  const a=rect(s,x,y,w,h,fill,C.teal);a.name=label.replace(/\n/g,' ');a.text=label;
  a.text.style={typeface:FONT,fontSize:size,color:C.ink,bold,alignment:'center',verticalAlignment:'middle',autoFit:'none',insets:12};return a;
}
function arrow(s,a,b,from='bottom',to='top'){const c=s.shapes.connect(a,b,{kind:'straight',fromSide:from,toSide:to,line:{fill:C.teal,width:2,style:'solid'},tail:{type:'arrow',width:'med',length:'med'}});c.bringToFront();return c;}
function base(title, kicker){const s=p.slides.add();s.background.fill=C.white;slides.push(s);text(s,kicker.toUpperCase(),64,36,1000,28,17,C.teal,true);text(s,title,64,82,1152,100,44,C.ink,true);line(s,64,664,1152);text(s,'CONTOSO  /  AWS PLATFORM',64,681,650,20,15,C.muted);text(s,String(slides.length).padStart(2,'0'),1160,679,56,22,16,C.muted,false,'right');return s;}
function notes(s, body, sources=[]){s.speakerNotes.text=body+'\n\nSources:\n'+sources.map(u=>'- '+u).join('\n');s.speakerNotes.setVisible(true);}
function section(s,label,body,x,y,w){text(s,label,x,y,w,42,28,C.teal,true);text(s,body,x,y+52,w,190,27,C.ink);}

// 1. Cover: the recommendation is visible immediately.
{
const s=p.slides.add();slides.push(s);s.background.fill=C.ink;
text(s,'CONTOSO',64,60,1100,34,22,'#B7DEE1',true);
text(s,'Infrastructure as Code\nfor the AWS landing zone',64,185,1140,180,60,C.white,true);
text(s,'Terraform for shared foundations\nAWS Control Tower for governance',64,430,1080,100,34,'#B7DEE1');
text(s,'Tool selection, ownership and a practical EKS example',64,631,1110,30,22,C.white);
notes(s,'Contoso needs a repeatable way to establish and evolve an AWS landing zone. My recommendation is Terraform for the shared infrastructure, with AWS Control Tower providing the multi-account governance baseline. The choice is based on operational ownership as much as syntax. CloudFormation remains a strong AWS-native alternative, and CDK can serve application teams that benefit from a programming language. I will compare those tradeoffs, explain the boundaries between them, and connect the decision to the EKS and database example in this submission. The enterprise landing zone is a proposed operating model. The hands-on repository is a deliberately smaller implementation, and live AWS verification still requires an AWS account.',[S.choose]);
}

// 2. Benefits tied to outcomes rather than a list of tool features.
{
const s=base('A landing zone must remain consistent as teams grow','Why infrastructure as code');
const rows=[
['Repeatable environments','Reusable definitions reduce manual differences between accounts.'],
['Reviewable changes','Git history and a proposed change show what will change and why.'],
['Clear ownership','Teams know which repository and pipeline control each resource.'],
['Recoverable foundations','Versioned definitions support rebuilding and controlled recovery.'],
['Ongoing governance','Controls, drift checks and evidence continue after deployment.'],
];
rows.forEach((r,i)=>{const y=205+i*82;text(s,r[0],64,y,358,52,29,C.teal,true);text(s,r[1],444,y,758,62,27);if(i<4)line(s,64,y+68,1152);});
notes(s,'The business problem is consistency as more teams use AWS. A landing zone establishes account structure, access, networking and security foundations. Infrastructure as code gives those choices a versioned definition. A reviewed change can be discussed before it affects a running service. Reusable definitions help teams begin from the same baseline, while repository and state boundaries make responsibility explicit. Recovery also improves because the intended configuration is recorded, although recovery still depends on backups and service-specific procedures. IaC alone does not guarantee security or eliminate drift. Contoso needs named owners, policy checks, controlled execution and follow-up monitoring. These are the outcomes I would use to judge the pilot, rather than choosing a tool only because its syntax is familiar. The benefits here are proposed delivery outcomes, not measured results from an existing Contoso deployment.',[S.choose,S.ct]);
}

// 3. Native editable comparison table.
{
const s=base('Three authoring models, two deployment engines','Comparison');
const values=[
['','Terraform','CloudFormation','AWS CDK'],
['Definition','HCL modules','YAML / JSON templates','Code and constructs'],
['Execution','Terraform + providers','CloudFormation stacks','Synthesizes CloudFormation'],
['State','Team-managed backend','AWS-managed stack state','AWS-managed stack state'],
['Strong fit','Shared, multi-provider foundations','AWS-native operations','Application teams using code'],
];
const t=s.tables.add({rows:5,columns:4,left:64,top:205,width:1152,height:390,columnWidths:[190,315,315,332],values});
t.borders.assign({fill:C.line,width:1,style:'solid'});
t.cells.block({row:0,column:0,rowCount:5,columnCount:4}).assign({textStyle:{typeface:FONT,fontSize:24,color:C.ink},margins:{left:16,right:16,top:12,bottom:12},anchor:'center'});
for(let r=0;r<5;r++){t.rows[r].height=r===0?62:82;for(let c=0;c<4;c++){const cell=t.getCell(r,c);cell.fill=r===0?C.ink:(r%2===0?C.pale:C.white);if(r===0){cell.text.style={typeface:FONT,fontSize:26,bold:true,color:C.white};}if(c===0&&r>0){cell.text.style={typeface:FONT,fontSize:24,bold:true,color:C.teal};}}}
text(s,'CDK uses CloudFormation to deploy and manage its stacks.',64,630,1152,30,24,C.muted);
notes(s,'This is the main distinction between the tools. Terraform has its own planning and execution engine and talks to services through providers. Its state records the mapping between configuration and managed resources, so the team must choose and operate a backend. CloudFormation takes templates and manages AWS stacks and their state as a service. CDK adds an authoring layer in a supported programming language. It synthesizes CloudFormation templates, which are then deployed through CloudFormation. That means CDK inherits stack lifecycle behavior, and operators still need to understand the generated resources. Terraform is attractive for a platform spanning several providers, while CloudFormation is attractive for an AWS-focused team seeking managed stack state. CDK is especially useful when application teams want tested abstractions in their existing language. The comparison expresses a fit, not an absolute capability boundary.',[S.terraform,S.cfnTemplate,S.cdk,S.state]);
}

{
const s=base('Terraform makes the shared platform explicit','Terraform');
section(s,'Benefits','Reusable modules and a reviewable plan\n\nOne workflow across AWS and other providers',64,210,540);
section(s,'Tradeoffs','State and provider lifecycle need an owner\n\nProvider coverage and upgrades require testing',676,210,540);
line(s,64,485,1152);
text(s,'Prerequisites',64,515,260,42,28,C.teal,true);
text(s,'HCL, AWS IAM, pinned dependencies and a secured remote state backend',350,514,852,90,29);
notes(s,'For Contoso I would use Terraform to define shared networks, common identity integrations and repeatable workload infrastructure. Modules provide a reusable contract, and a plan makes proposed resource changes visible during review. The benefit of multiple providers is relevant when the platform also integrates Kubernetes, DNS or other services. The cost is operational responsibility. State can contain sensitive information and must be protected, backed up and locked during changes. The platform team also owns provider and module updates, import procedures and recovery from interrupted applies. Prerequisites therefore include HCL and AWS IAM knowledge, dependency management and a reliable backend. I would begin with a small set of maintained modules and document their supported inputs, rather than building a large abstraction framework before the first workload. The recommendation assumes Contoso is willing to operate that workflow.',[S.terraform,S.state]);
}

{
const s=base('CloudFormation keeps stack operations inside AWS','CloudFormation');
section(s,'Benefits','AWS manages stack state\n\nChange sets, rollback and StackSets',64,210,540);
section(s,'Tradeoffs','AWS-focused resource lifecycle\n\nLarge templates can become hard to maintain',676,210,540);
line(s,64,485,1152);
text(s,'Prerequisites',64,515,260,42,28,C.teal,true);
text(s,'YAML / JSON, IAM, stack boundaries and replacement / rollback knowledge',350,514,852,90,29);
notes(s,'CloudFormation is a credible alternative for an AWS-only landing zone. AWS operates the stack state, so there is no separate Terraform backend to secure and maintain. Change sets expose proposed updates, StackSets support distribution across accounts and Regions, and rollback behavior helps when a deployment fails. Those protections still require operational understanding. A resource replacement can affect data, and rollback is not a replacement for a database backup. Templates use JSON or YAML, and large stacks need clear boundaries and reuse conventions to remain understandable. The team should know deployment permissions, cross-stack dependencies and how to recover a failed stack. I would prefer CloudFormation if Contoso deliberately standardized on AWS-native operations and placed a high value on managed state. Its suitability is not reduced by its declarative syntax. The choice depends on the team and its surrounding platform.',[S.cfn,S.cfnTemplate]);
}

{
const s=base('CDK gives application teams a code-based interface','AWS Cloud Development Kit');
const a=node(s,'Application code\nand constructs',64,210,330,110);
const b=node(s,'Synthesized\nCloudFormation',475,210,330,110);
const c=node(s,'AWS stack\nand resources',886,210,330,110);
arrow(s,a,b,'right','left');arrow(s,b,c,'right','left');
section(s,'Benefits','Familiar languages, reusable constructs\nand software testing patterns',64,380,540);
section(s,'Tradeoffs','Generated templates and dependencies\nstill need operational review',676,380,540);
text(s,'Prerequisites: language tooling, Node.js, CDK CLI, AWS identity and bootstrap resources',64,600,1152,50,25,C.muted);
notes(s,'CDK lets a team describe infrastructure in a supported language and package reusable constructs. It can fit an application team that already tests and reviews code in TypeScript, Python or another supported language. The deployment flow is important: the code synthesizes a CloudFormation template and CloudFormation deploys the stack. Code tests do not prove that a deployment will succeed, and the generated template still needs inspection for permissions and replacements. CDK also adds dependency and toolchain management. Developers need the language prerequisites, Node.js for the shared backend, the CDK CLI and AWS credentials. Each target environment needs bootstrap resources, including asset storage and deployment roles. I would allow CDK for application-owned resources when the team can operate this lifecycle and consumes clear interfaces to shared infrastructure. It should not independently manage the same resources already owned by Terraform.',[S.cdk,S.cdkPrereq,S.cdkBootstrap]);
}

{
const s=base('Each layer has a single lifecycle owner','Recommendation');
const layers=[
['Governance','AWS Control Tower','Central cloud / security team'],
['Account provisioning','Account Factory for Terraform','Account vending team'],
['Shared foundations','Terraform modules and pipelines','Platform team'],
['Applications','Terraform or CDK within a boundary','Application team'],
];
layers.forEach((r,i)=>{let y=200+i*96;rect(s,64,y,1152,78,i%2?C.pale:C.blue,C.line);text(s,r[0],84,y+15,270,52,26,C.teal,true);text(s,r[1],370,y+15,440,52,26,C.ink,true);text(s,r[2],832,y+15,365,52,24,C.muted);});
text(s,'AFT provisions and customizes accounts. Workload resources use their own delivery pipelines.',64,606,1152,46,24,C.muted);
notes(s,'The recommendation combines a governance service with an infrastructure workflow. Control Tower establishes and governs the multi-account environment, including controls and centralized oversight. Where Terraform-based account requests are useful, AFT can automate provisioning and account customizations. It requires an existing Control Tower landing zone and a separate AFT management account. AWS explicitly limits AFT to the account provisioning and customization purpose, so the EKS workload is delivered by a separate pipeline. The platform team owns shared foundation modules. Application teams may use Terraform or CDK for resources inside an agreed boundary. One physical resource has one lifecycle owner. Teams exchange identifiers and supported interfaces instead of having several state files or stacks control it. This ownership split is my proposed operating model for Contoso. It needs agreement from security, platform operations and application teams before enterprise adoption.',[S.ct,S.aft,S.choose]);
}

{
const s=base('Delivery combines change review with protected state','Delivery workflow');
const labels=['Git change\nand review','Validate, test\nand plan','Approved\napply','Observe\nand detect drift'];
const ns=labels.map((v,i)=>node(s,v,64+i*296,210,264,100));ns.slice(0,-1).forEach((a,i)=>arrow(s,a,ns[i+1],'right','left'));
section(s,'State protection','Encrypted, versioned S3 backend\nS3 lockfile prevents concurrent writes\nSeparate state by lifecycle and owner',64,390,540);
section(s,'Execution identity','Short-lived AWS identity in CI\nLeast-privilege deployment roles\nProtected approvals and audit evidence',676,390,540);
notes(s,'The workflow starts with a reviewed Git change. Validation and tests catch errors early, while a plan provides concrete evidence of the proposed infrastructure change. An authorized pipeline applies the reviewed result, then operators inspect service health and drift. For Terraform state, the proposed S3 backend uses encryption, versioning and native S3 lockfile locking. Locking prevents concurrent state writers. It does not validate a change or make an apply transactional. Current HashiCorp guidance deprecates the older DynamoDB locking mechanism, so this submission uses use_lockfile. I would keep state boundaries aligned with owners and lifecycles, with limited access to state and saved plans because they may contain secrets. CI should obtain short-lived credentials through federation. In the hands-on repository, bootstrap, infrastructure and Kubernetes platform are separate roots so the cluster exists before Kubernetes providers connect to it. This is the proposed delivery workflow, not a claim that a remote CI system has already run it.',[S.s3,S.state]);
}

{
const s=base('Private compute and data behind public ingress','EKS and PostgreSQL');
rect(s,216,200,660,438,C.pale,C.line);
text(s,'VPC across two Availability Zones',236,216,620,34,25,C.teal,true);
const alb=node(s,'Public ALB\npublic subnets across two AZs',300,265,500,70,{size:24});
const eks=node(s,'EKS frontend / API pods\nmanaged nodes in private subnets',300,380,500,76,{size:24});
const db=node(s,'RDS PostgreSQL\nisolated DB subnets across two AZs',300,510,500,80,{size:24});
arrow(s,alb,eks);arrow(s,eks,db);
text(s,'HTTP to app',575,345,225,34,22,C.muted);
text(s,'5432 / verified TLS',575,474,280,34,22,C.muted);
const client=text(s,'Internet\nclient',84,278,125,62,23,C.ink,true);arrow(s,client,alb,'right','left');
text(s,'Ingress',916,215,300,36,28,C.teal,true);
text(s,'Regional WAF\nACM HTTPS with owned DNS',916,262,300,100,25);
text(s,'Workload identity',916,388,300,36,28,C.teal,true);
text(s,'App IRSA role → DB IAM auth\nBootstrap role → master secret',916,435,300,120,24);
text(s,'AWS integration verification is pending an AWS account.',916,576,300,66,22,C.orange,true);
notes(s,'This editable diagram connects the recommendation to the assignment implementation. The public Application Load Balancer spans public subnets. It sends application traffic to pods running on EKS managed nodes in private subnets. PostgreSQL runs in an isolated database subnet group, and security groups allow only the required database path. The app uses IAM database authentication over verified TLS. A separate bootstrap role reads the managed master secret to create the application database user, while the steady-state app role does not need that secret. The regional WAF is configurable and enabled by default. Valid browser HTTPS requires an owned DNS name and a matching ACM certificate. An AWS-owned ALB hostname cannot be presented as if a certificate for our own domain covered it. The database subnet group covers two Availability Zones, but the demo database instance itself is single-AZ. AWS connectivity, IAM behavior, ALB routing and live database access still require integration verification after an account is available. This is a design and code demonstration, not evidence of a completed AWS deployment.');
}

{
const s=base('A pilot establishes the foundation for wider rollout','Decision and next steps');
section(s,'Demonstration choices','One NAT gateway and one RDS instance\nSmall EKS node group\nExplicit access and database boundaries',64,210,540);
section(s,'Production decisions','AZ failure tolerance and database recovery\nPrivate administration and verified HTTPS\nLogging, patching, budgets and policy ownership',676,210,540);
line(s,64,500,1152);
text(s,'Recommended next step',64,532,350,38,28,C.teal,true);
text(s,'Pilot Terraform foundations under Control Tower governance.\nAgree owners and acceptance checks before wider rollout.',64,584,1152,68,28,C.ink,true);
notes(s,'The practical submission favors understandable, controlled scope. A single NAT gateway and a single RDS instance reduce the number of resources and recurring costs for a demonstration, but they do not provide full Availability Zone resilience. Production sizing, database Multi-AZ configuration, recovery objectives and backup restoration need explicit decisions. Administrative access should use an appropriate private network path, and internet users need a valid domain and certificate. Operational ownership also includes logs, metrics, patching, budget alerts and drift response. Before wider adoption I would pilot the Terraform foundation in a governed account, perform a reviewed change, verify application to database access, test a recovery procedure and record the outcome. The final decision is Terraform for shared foundations with Control Tower for governance, plus CloudFormation or CDK where a team has a clear and isolated lifecycle boundary. Live AWS checks remain a prerequisite for claiming the hands-on assignment works in AWS.');
}

slides[6].speakerNotes.text=slides[6].speakerNotes.text.replace('\n\nSources:', '\n\nThe central cloud team owns the account and OU model, the logging and audit accounts, and decisions about guardrail exceptions. Terraform must respect resources owned by Control Tower.\n\nSources:');
slides[8].speakerNotes.text+='- '+S.irsa+'\n- '+S.rdsIam+'\n\nImplementation references in this repository: infra/network.tf, infra/database.tf, infra/identity.tf, platform/ingress.tf and platform/workload.tf.';
await fs.mkdir(path.join(workspaceDir,'.build'),{recursive:true});
await fs.mkdir(path.join(workspaceDir,'output'),{recursive:true});
const preview=path.join(workspaceDir,'.build','previews');await fs.mkdir(preview,{recursive:true});
for(let i=0;i<slides.length;i++){
 const stem=`slide-${String(i+1).padStart(2,'0')}`;
 const png=await p.export({slide:slides[i],format:'png',scale:1});
 await fs.writeFile(path.join(preview,stem+'.png'),new Uint8Array(await png.arrayBuffer()));
 const layout=await slides[i].export({format:'layout'});await fs.writeFile(path.join(preview,stem+'.layout.json'),await layout.text());
}
const notesMarkdown=['# Speaker notes','English stakeholder presentation for Contoso. Suggested delivery length follows the assignment: 10–15 minutes.','',...slides.flatMap((s,i)=>[`## ${i+1}. ${i===0?'Infrastructure as Code for Contoso':s.shapes.items.find(a=>a.text?.toString?.()&&a.position.top===82)?.text?.toString?.()??'Slide'}`,s.speakerNotes.text,''])].join('\n\n');
await fs.writeFile(path.join(workspaceDir,'speaker-notes.md'),notesMarkdown);
const candidatePath=path.join(workspaceDir,'.build','contoso-iac-candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
const finalName=process.env.PRESENTATION_OUTPUT_NAME??'contoso-iac-stakeholder.pptx';
const result=await finalizePresentation({
 explicitTotalSlideCount:10,requiredNativeTableOwnerSlides:[3],requiredNativeChartOwnerSlides:[],
 workspaceDir,candidatePath,finalPath:path.join(workspaceDir,'output',finalName),pythonExecutable:RUNTIME_PYTHON,
 integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','3'],
 fontPolicy:{basis:'design',families:[FONT]},verifyArtifactToolImport:true,
 receiptPath:path.join(workspaceDir,'.build',finalName+'.validation.json'),
});
console.log(JSON.stringify(result,null,2));
