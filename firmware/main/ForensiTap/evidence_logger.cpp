#include "evidence_logger.h"
#include <string.h>

ForensiTapEvidenceLogger g_evidenceLogger;

ForensiTapEvidenceLogger::ForensiTapEvidenceLogger()
    : m_storedBlockCount(0),
      m_totalBlocksCreated(0),
      m_isInitialized(false) {
    memset(m_genesisHash, 0, sizeof(m_genesisHash));
    memset(m_tipHash, 0, sizeof(m_tipHash));
    memset(m_blocks, 0, sizeof(m_blocks));
}

bool ForensiTapEvidenceLogger::init(const SystemConfig& config) {
    (void)config;
    LOG_INFO("EVID", "Initializing Forensic Evidence Logging Subsystem (SHA-256 Hash Chain)...");

    m_storedBlockCount = 0;
    m_totalBlocksCreated = 0;
    mintGenesisBlock();
    m_isInitialized = true;

    LOG_INFO("EVID", "Evidence Chain Initialized. Genesis Block Hash: %.16s...", m_genesisHash);
    return true;
}

void ForensiTapEvidenceLogger::update(unsigned long currentMillis) {
    (void)currentMillis;
    // Passive subsystem: blocks minted synchronously on events
}

bool ForensiTapEvidenceLogger::isHealthy() const {
    if (!m_isInitialized) return false;
    ChainVerificationResult res = verifyChainIntegrity();
    return res.isValid;
}

bool ForensiTapEvidenceLogger::computeSha256Hex(const char* input, size_t inputLen, char* outHex65) {
    if (!input || !outHex65) return false;

    unsigned char hashBytes[32];
    int ret = mbedtls_sha256((const unsigned char*)input, inputLen, hashBytes, 0 /* 0 = SHA-256 */);
    if (ret != 0) return false;

    for (int i = 0; i < 32; ++i) {
        snprintf(outHex65 + (i * 2), 3, "%02x", hashBytes[i]);
    }
    outHex65[64] = '\0';
    return true;
}

void ForensiTapEvidenceLogger::buildCanonicalString(char* dest, size_t maxLen,
                                                   uint32_t index, uint32_t timestampMs,
                                                   const char* eventType, const char* severity,
                                                   const char* description, const char* prevHash) {
    if (!dest || maxLen == 0) return;
    snprintf(dest, maxLen, "%u|%u|%s|%s|%s|%s",
             index,
             timestampMs,
             eventType ? eventType : "UNKNOWN",
             severity ? severity : "INFO",
             description ? description : "",
             prevHash ? prevHash : GENESIS_PREV_HASH);
}

void ForensiTapEvidenceLogger::mintGenesisBlock() {
    EvidenceBlock& block = m_blocks[0];
    block.index = 0;
    block.timestampMs = millis();
    strncpy(block.eventType, "SYSTEM_BOOT", sizeof(block.eventType) - 1);
    block.eventType[sizeof(block.eventType) - 1] = '\0';
    strncpy(block.severity, "INFO", sizeof(block.severity) - 1);
    block.severity[sizeof(block.severity) - 1] = '\0';
    strncpy(block.description, "Genesis block: ForensiTap evidence chain initialized", sizeof(block.description) - 1);
    block.description[sizeof(block.description) - 1] = '\0';
    strncpy(block.prevHash, GENESIS_PREV_HASH, sizeof(block.prevHash) - 1);
    block.prevHash[sizeof(block.prevHash) - 1] = '\0';

    char canonical[256];
    buildCanonicalString(canonical, sizeof(canonical),
                         block.index, block.timestampMs,
                         block.eventType, block.severity,
                         block.description, block.prevHash);

    computeSha256Hex(canonical, strlen(canonical), block.blockHash);

    strncpy(m_genesisHash, block.blockHash, sizeof(m_genesisHash) - 1);
    m_genesisHash[sizeof(m_genesisHash) - 1] = '\0';
    strncpy(m_tipHash, block.blockHash, sizeof(m_tipHash) - 1);
    m_tipHash[sizeof(m_tipHash) - 1] = '\0';

    m_storedBlockCount = 1;
    m_totalBlocksCreated = 1;
}

void ForensiTapEvidenceLogger::logEvidence(const char* eventType, const char* severity, const char* description) {
    if (!m_isInitialized) return;

    uint32_t nextIndex = m_totalBlocksCreated;
    uint32_t nowMs = millis();

    uint16_t slot = 0;
    if (m_storedBlockCount < MAX_EVIDENCE_BLOCKS) {
        slot = m_storedBlockCount;
        m_storedBlockCount++;
    } else {
        // Shift left (FIFO window eviction to preserve memory)
        memmove(&m_blocks[0], &m_blocks[1], sizeof(EvidenceBlock) * (MAX_EVIDENCE_BLOCKS - 1));
        slot = MAX_EVIDENCE_BLOCKS - 1;
    }

    EvidenceBlock& block = m_blocks[slot];
    block.index = nextIndex;
    block.timestampMs = nowMs;

    strncpy(block.eventType, eventType ? eventType : "ALERT", sizeof(block.eventType) - 1);
    block.eventType[sizeof(block.eventType) - 1] = '\0';

    strncpy(block.severity, severity ? severity : "INFO", sizeof(block.severity) - 1);
    block.severity[sizeof(block.severity) - 1] = '\0';

    strncpy(block.description, description ? description : "", sizeof(block.description) - 1);
    block.description[sizeof(block.description) - 1] = '\0';

    strncpy(block.prevHash, m_tipHash, sizeof(block.prevHash) - 1);
    block.prevHash[sizeof(block.prevHash) - 1] = '\0';

    char canonical[256];
    buildCanonicalString(canonical, sizeof(canonical),
                         block.index, block.timestampMs,
                         block.eventType, block.severity,
                         block.description, block.prevHash);

    computeSha256Hex(canonical, strlen(canonical), block.blockHash);

    // Update chain tip to newly minted block
    strncpy(m_tipHash, block.blockHash, sizeof(m_tipHash) - 1);
    m_tipHash[sizeof(m_tipHash) - 1] = '\0';

    m_totalBlocksCreated++;

    LOG_INFO("EVID", "Minted block #%u [%s] Hash: %.16s...",
             block.index, block.eventType, block.blockHash);
}

ChainVerificationResult ForensiTapEvidenceLogger::verifyChainIntegrity() const {
    ChainVerificationResult res;
    res.isValid = true;
    res.checkedBlocks = m_storedBlockCount;
    res.failedIndex = 0;
    res.failureReason[0] = '\0';

    if (m_storedBlockCount == 0) {
        res.isValid = false;
        strncpy(res.failureReason, "Evidence chain is empty", sizeof(res.failureReason) - 1);
        return res;
    }

    char expectedHash[65];
    char canonical[256];

    for (uint16_t i = 0; i < m_storedBlockCount; ++i) {
        const EvidenceBlock& b = m_blocks[i];

        // 1. Genesis block check (if present at index 0)
        if (b.index == 0) {
            if (strcmp(b.prevHash, GENESIS_PREV_HASH) != 0) {
                res.isValid = false;
                res.failedIndex = b.index;
                strncpy(res.failureReason, "Invalid Genesis prev_hash", sizeof(res.failureReason) - 1);
                return res;
            }
        } else if (i > 0) {
            // 2. Hash link continuity check with previous stored block
            const EvidenceBlock& prev = m_blocks[i - 1];
            if (b.index != prev.index + 1) {
                res.isValid = false;
                res.failedIndex = b.index;
                strncpy(res.failureReason, "Sequence index discontinuity", sizeof(res.failureReason) - 1);
                return res;
            }
            if (strcmp(b.prevHash, prev.blockHash) != 0) {
                res.isValid = false;
                res.failedIndex = b.index;
                strncpy(res.failureReason, "Broken hash link to previous block", sizeof(res.failureReason) - 1);
                return res;
            }
        }

        // 3. Cryptographic digest verification
        buildCanonicalString(canonical, sizeof(canonical),
                             b.index, b.timestampMs,
                             b.eventType, b.severity,
                             b.description, b.prevHash);

        computeSha256Hex(canonical, strlen(canonical), expectedHash);

        if (strcmp(expectedHash, b.blockHash) != 0) {
            res.isValid = false;
            res.failedIndex = b.index;
            strncpy(res.failureReason, "Cryptographic digest mismatch (Tampered)", sizeof(res.failureReason) - 1);
            return res;
        }
    }

    return res;
}

void ForensiTapEvidenceLogger::printDiagnostics() {
    ChainVerificationResult ver = verifyChainIntegrity();

    Serial.println("  +-- [Forensic Evidence Subsystem: EVID]");
    Serial.printf("  |   Chain Integrity : %s\n", ver.isValid ? "VALID (Cryptographically Intact)" : "TAMPERED / INVALID");
    Serial.printf("  |   Blocks Minted   : %u total | Window: %u / %u stored\n", m_totalBlocksCreated, m_storedBlockCount, MAX_EVIDENCE_BLOCKS);
    Serial.printf("  |   Genesis Hash    : %.24s...\n", m_genesisHash);
    Serial.printf("  |   Chain Tip Hash  : %.24s...\n", m_tipHash);

    if (!ver.isValid) {
        Serial.printf("  |   FAILURE NOTICE  : Block #%u: %s\n", ver.failedIndex, ver.failureReason);
    }

    Serial.println("  +------------------------------------");
}
