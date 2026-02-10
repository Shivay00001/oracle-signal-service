# DAO Governance Framework

## Purpose

The DAO exists to manage shared assets, enforce governance rules, and coordinate decision-making through on-chain proposals and voting.

## Structure

- **Founder**: Originator and initial administrator
- **Guardian**: Smart contract-based execution layer for governance decisions
- **Council**: 5–10 appointed members with oversight responsibilities
- **Treasury**: Multi-signature wallet (Gnosis Safe) for fund management
- **IP Licensing**: All intellectual property is DAO-managed with on-chain license records

## Governance Rules

1. Every decision requires a formal proposal and vote (Snapshot / Aragon compatible).
2. Voting power is calculated from:
   - Stake amount (ETH locked in DAO contract)
   - Time-weighted staking duration
3. Proposals require majority approval to execute.
4. The AI Guardian contract can provide advisory signals (confidence scores), but cannot unilaterally override votes.

## Treasury Allocation

| Category | Percentage |
|---|---|
| Reinvestment in development | 40% |
| Contributor compensation | 30% |
| Reserves | 30% |

## Succession Protocol

If the founder becomes inactive (no heartbeat within configured interval):

1. The Guardian contract marks the founder as inactive.
2. Certified successors (readiness score ≥ 80) can assume administrative functions.
3. The DAO continues operating under the existing constitution and smart contract rules.

## IP Licensing

All IP (code, algorithms, documentation) is governed by the DAO. Usage requires:

- Signed license agreement (on-chain or off-chain)
- Royalty terms defined per license
- Public record of license on-chain

## Smart Contracts

| Contract | Purpose |
|---|---|
| `YOUDAO` | Core governance: proposals, voting, staking, IP licensing |
| `YOUAIGuardian` | AI oracle integration, heartbeat monitoring, successor management |
| `TreasuryMultiSig` | Multi-sig fund management |
