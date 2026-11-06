# Contoso IaC presentation

Part 1 of the assignment: an 11-slide, 10–15 minute stakeholder presentation on delivering Contoso's AWS landing zone with Infrastructure as Code.

- [contoso-iac-stakeholder.key](contoso-iac-stakeholder.key): the deck (Keynote), with presenter notes
- [contoso-iac-stakeholder.pdf](contoso-iac-stakeholder.pdf): the same deck as PDF, for anyone without Keynote
- [notes.md](notes.md): slide text, speaker notes, sources and answers to likely questions

It starts with the risks of building AWS by hand, then covers the benefits of IaC, compares Terraform, CloudFormation and the AWS CDK (pros, cons, prerequisites), and recommends **CloudFormation on AWS Control Tower** for the shared foundation. The account model is one account per application per environment under Prod and Non-prod OUs, with costs rolled up to departments and projects through AWS Cost Categories.

The Keynote file is the source. After editing it, export the PDF again (**File › Export To › PDF**) and keep `notes.md` in step. Earlier versions are in Git history.
