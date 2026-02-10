import { expect } from "chai";
import { ethers } from "hardhat";
import { YOUDAO, YOUAIGuardian, TreasuryMultiSig } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("YOUDAO Immortal Execution System", function () {
  let dao: YOUDAO;
  let guardian: YOUAIGuardian;
  let treasury: TreasuryMultiSig;
  let founder: SignerWithAddress;
  let oracle: SignerWithAddress;
  let staker1: SignerWithAddress;
  let staker2: SignerWithAddress;
  let licensee: SignerWithAddress;

  const MIN_STAKE = ethers.parseEther("0.1");
  const VOTING_PERIOD = 7 * 24 * 60 * 60;
  const HEARTBEAT_INTERVAL = 7 * 24 * 60 * 60;

  beforeEach(async function () {
    [founder, oracle, staker1, staker2, licensee] = await ethers.getSigners();

    const TreasuryMultiSig = await ethers.getContractFactory("TreasuryMultiSig");
    treasury = await TreasuryMultiSig.deploy([founder.address], 1);
    await treasury.waitForDeployment();

    const YOUDAO = await ethers.getContractFactory("YOUDAO");
    dao = await YOUDAO.deploy(founder.address, await treasury.getAddress());
    await dao.waitForDeployment();

    const YOUAIGuardian = await ethers.getContractFactory("YOUAIGuardian");
    guardian = await YOUAIGuardian.deploy(founder.address, HEARTBEAT_INTERVAL);
    await guardian.waitForDeployment();

    await dao.setAIGuardian(await guardian.getAddress());
    await guardian.setYOUDAO(await dao.getAddress());
    await guardian.setAIOracle(oracle.address);
  });

  describe("Deployment", function () {
    it("Should set the correct founder", async function () {
      expect(await dao.founderAddress()).to.equal(founder.address);
    });

    it("Should link DAO and Guardian correctly", async function () {
      expect(await dao.aiGuardianAddress()).to.equal(await guardian.getAddress());
      expect(await guardian.youDAOAddress()).to.equal(await dao.getAddress());
    });

    it("Should set initial founder as active", async function () {
      expect(await guardian.founderActive()).to.equal(true);
    });
  });

  describe("Staking", function () {
    it("Should allow users to stake", async function () {
      await dao.connect(staker1).stake({ value: MIN_STAKE });
      const stakeInfo = await dao.stakes(staker1.address);
      expect(stakeInfo.amount).to.equal(MIN_STAKE);
    });

    it("Should reject stakes below minimum", async function () {
      await expect(
        dao.connect(staker1).stake({ value: ethers.parseEther("0.05") })
      ).to.be.revertedWith("Stake too low");
    });

    it("Should calculate voting power correctly", async function () {
      await dao.connect(staker1).stake({ value: MIN_STAKE });
      const votingPower = await dao.getVotingPower(staker1.address);
      expect(votingPower).to.be.gt(MIN_STAKE);
    });

    it("Should allow unstaking", async function () {
      await dao.connect(staker1).stake({ value: MIN_STAKE });
      await dao.connect(staker1).unstake(MIN_STAKE);
      const stakeInfo = await dao.stakes(staker1.address);
      expect(stakeInfo.amount).to.equal(0);
    });
  });

  describe("Proposal Creation and Voting", function () {
    beforeEach(async function () {
      await dao.connect(staker1).stake({ value: MIN_STAKE });
      await dao.connect(staker2).stake({ value: ethers.parseEther("0.2") });
    });

    it("Should allow stakers to create proposals", async function () {
      await dao.connect(staker1).createProposal(
        "Test Proposal",
        "Description",
        ethers.parseEther("1"),
        staker2.address,
        0
      );

      const proposal = await dao.proposals(1);
      expect(proposal.title).to.equal("Test Proposal");
      expect(proposal.proposer).to.equal(staker1.address);
    });

    it("Should not allow non-stakers to create proposals", async function () {
      await expect(
        dao.connect(licensee).createProposal(
          "Test",
          "Desc",
          0,
          staker1.address,
          0
        )
      ).to.be.revertedWith("Must be staker");
    });

    it("Should allow voting on proposals", async function () {
      await dao.connect(staker1).createProposal(
        "Test",
        "Desc",
        0,
        staker2.address,
        0
      );

      await dao.connect(staker1).vote(1, true);
      const proposal = await dao.proposals(1);
      expect(proposal.forVotes).to.be.gt(0);
    });

    it("Should prevent double voting", async function () {
      await dao.connect(staker1).createProposal(
        "Test",
        "Desc",
        0,
        staker2.address,
        0
      );

      await dao.connect(staker1).vote(1, true);
      await expect(dao.connect(staker1).vote(1, true)).to.be.revertedWith(
        "Already voted"
      );
    });
  });

  describe("AI Guardian Integration", function () {
    beforeEach(async function () {
      await dao.connect(staker1).stake({ value: MIN_STAKE });
    });

    it("Should record AI decisions", async function () {
      await dao.connect(staker1).createProposal(
        "Test",
        "Desc",
        0,
        staker2.address,
        0
      );

      await guardian.connect(oracle).makeAIDecision(
        1,
        true,
        85,
        "AI approved based on vision alignment"
      );

      const proposal = await dao.proposals(1);
      expect(proposal.aiApproved).to.equal(true);
      expect(proposal.aiConfidence).to.equal(85);
    });

    it("Should only allow oracle to make AI decisions", async function () {
      await dao.connect(staker1).createProposal(
        "Test",
        "Desc",
        0,
        staker2.address,
        0
      );

      await expect(
        guardian.connect(staker1).makeAIDecision(1, true, 85, "Test")
      ).to.be.revertedWith("Only AI Oracle");
    });
  });

  describe("Founder Heartbeat", function () {
    it("Should update heartbeat", async function () {
      const beforeHeartbeat = await guardian.lastHeartbeat();
      await ethers.provider.send("evm_increaseTime", [3600]);
      await ethers.provider.send("evm_mine", []);
      
      await guardian.connect(founder).heartbeat();
      const afterHeartbeat = await guardian.lastHeartbeat();
      
      expect(afterHeartbeat).to.be.gt(beforeHeartbeat);
    });

    it("Should mark founder as inactive after timeout", async function () {
      await ethers.provider.send("evm_increaseTime", [HEARTBEAT_INTERVAL + 1]);
      await ethers.provider.send("evm_mine", []);
      
      await guardian.checkFounderStatus();
      expect(await guardian.founderActive()).to.equal(false);
    });
  });

  describe("IP Licensing", function () {
    it("Should allow founder to issue licenses", async function () {
      await dao.connect(founder).issueLicense(
        "YOU.AI Algorithm",
        "Software",
        licensee.address,
        1000,
        365 * 24 * 60 * 60
      );

      const license = await dao.licenses(1);
      expect(license.ipName).to.equal("YOU.AI Algorithm");
      expect(license.licensee).to.equal(licensee.address);
    });

    it("Should collect royalty payments", async function () {
      await dao.connect(founder).issueLicense(
        "YOU.AI",
        "Software",
        licensee.address,
        1000,
        365 * 24 * 60 * 60
      );

      const royaltyAmount = ethers.parseEther("0.1");
      await dao.connect(licensee).payRoyalty(1, { value: royaltyAmount });

      const license = await dao.licenses(1);
      expect(license.totalRoyaltiesPaid).to.equal(royaltyAmount);
    });
  });

  describe("Treasury Integration", function () {
    it("Should transfer funds to treasury", async function () {
      const amount = ethers.parseEther("1");
      await founder.sendTransaction({
        to: await treasury.getAddress(),
        value: amount,
      });

      const balance = await ethers.provider.getBalance(await treasury.getAddress());
      expect(balance).to.equal(amount);
    });
  });

  describe("Council Management", function () {
    it("Should allow founder to add council members", async function () {
      await dao.connect(founder).addCouncilMember(staker1.address);
      expect(await dao.isCouncilMember(staker1.address)).to.equal(true);
    });

    it("Should prevent non-founder from adding council members", async function () {
      await expect(
        dao.connect(staker1).addCouncilMember(staker2.address)
      ).to.be.revertedWith("Only founder");
    });
  });

  describe("Successor Management", function () {
    it("Should allow adding successors", async function () {
      await guardian.connect(founder).addSuccessor(
        staker1.address,
        "AI Research"
      );

      const successor = await guardian.successors(1);
      expect(successor.addr).to.equal(staker1.address);
      expect(successor.specialization).to.equal("AI Research");
    });

    it("Should track successor readiness", async function () {
      await guardian.connect(founder).addSuccessor(
        staker1.address,
        "Development"
      );

      await guardian.connect(founder).updateSuccessorReadiness(1, 85);
      const successor = await guardian.successors(1);
      expect(successor.readinessScore).to.equal(85);
      expect(successor.certified).to.equal(true);
    });
  });
});