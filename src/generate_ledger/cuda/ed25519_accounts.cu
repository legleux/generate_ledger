// =========================================================================
// Utility
// =========================================================================

__device__ unsigned int load_4(const unsigned char *s) {
    return (unsigned int)s[0]
         | ((unsigned int)s[1] << 8)
         | ((unsigned int)s[2] << 16)
         | ((unsigned int)s[3] << 24);
}

__device__ unsigned int load_3(const unsigned char *s) {
    return (unsigned int)s[0]
         | ((unsigned int)s[1] << 8)
         | ((unsigned int)s[2] << 16);
}

// =========================================================================
// SHA-512  (single-block: up to 111 bytes input)
// =========================================================================

__constant__ unsigned long long SHA512_K[80] = {
    0x428a2f98d728ae22ULL, 0x7137449123ef65cdULL, 0xb5c0fbcfec4d3b2fULL, 0xe9b5dba58189dbbcULL,
    0x3956c25bf348b538ULL, 0x59f111f1b605d019ULL, 0x923f82a4af194f9bULL, 0xab1c5ed5da6d8118ULL,
    0xd807aa98a3030242ULL, 0x12835b0145706fbeULL, 0x243185be4ee4b28cULL, 0x550c7dc3d5ffb4e2ULL,
    0x72be5d74f27b896fULL, 0x80deb1fe3b1696b1ULL, 0x9bdc06a725c71235ULL, 0xc19bf174cf692694ULL,
    0xe49b69c19ef14ad2ULL, 0xefbe4786384f25e3ULL, 0x0fc19dc68b8cd5b5ULL, 0x240ca1cc77ac9c65ULL,
    0x2de92c6f592b0275ULL, 0x4a7484aa6ea6e483ULL, 0x5cb0a9dcbd41fbd4ULL, 0x76f988da831153b5ULL,
    0x983e5152ee66dfabULL, 0xa831c66d2db43210ULL, 0xb00327c898fb213fULL, 0xbf597fc7beef0ee4ULL,
    0xc6e00bf33da88fc2ULL, 0xd5a79147930aa725ULL, 0x06ca6351e003826fULL, 0x142929670a0e6e70ULL,
    0x27b70a8546d22ffcULL, 0x2e1b21385c26c926ULL, 0x4d2c6dfc5ac42aedULL, 0x53380d139d95b3dfULL,
    0x650a73548baf63deULL, 0x766a0abb3c77b2a8ULL, 0x81c2c92e47edaee6ULL, 0x92722c851482353bULL,
    0xa2bfe8a14cf10364ULL, 0xa81a664bbc423001ULL, 0xc24b8b70d0f89791ULL, 0xc76c51a30654be30ULL,
    0xd192e819d6ef5218ULL, 0xd69906245565a910ULL, 0xf40e35855771202aULL, 0x106aa07032bbd1b8ULL,
    0x19a4c116b8d2d0c8ULL, 0x1e376c085141ab53ULL, 0x2748774cdf8eeb99ULL, 0x34b0bcb5e19b48a8ULL,
    0x391c0cb3c5c95a63ULL, 0x4ed8aa4ae3418acbULL, 0x5b9cca4f7763e373ULL, 0x682e6ff3d6b2b8a3ULL,
    0x748f82ee5defb2fcULL, 0x78a5636f43172f60ULL, 0x84c87814a1f0ab72ULL, 0x8cc702081a6439ecULL,
    0x90befffa23631e28ULL, 0xa4506cebde82bde9ULL, 0xbef9a3f7b2c67915ULL, 0xc67178f2e372532bULL,
    0xca273eceea26619cULL, 0xd186b8c721c0c207ULL, 0xeada7dd6cde0eb1eULL, 0xf57d4f7fee6ed178ULL,
    0x06f067aa72176fbaULL, 0x0a637dc5a2c898a6ULL, 0x113f9804bef90daeULL, 0x1b710b35131c471bULL,
    0x28db77f523047d84ULL, 0x32caab7b40c72493ULL, 0x3c9ebe0a15c9bebcULL, 0x431d67c49c100d4cULL,
    0x4cc5d4becb3e42b6ULL, 0x597f299cfc657e2aULL, 0x5fcb6fab3ad6faecULL, 0x6c44198c4a475817ULL
};

#define ROR64(x, n) (((x) >> (n)) | ((x) << (64 - (n))))
#define SHA512_CH(x,y,z)  (((x) & (y)) ^ (~(x) & (z)))
#define SHA512_MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define SHA512_S0(x) (ROR64(x,28) ^ ROR64(x,34) ^ ROR64(x,39))
#define SHA512_S1(x) (ROR64(x,14) ^ ROR64(x,18) ^ ROR64(x,41))
#define SHA512_s0(x) (ROR64(x,1)  ^ ROR64(x,8)  ^ ((x) >> 7))
#define SHA512_s1(x) (ROR64(x,19) ^ ROR64(x,61) ^ ((x) >> 6))

// SHA-512 of a single block (up to 111 bytes of data).
// Output: 64 bytes (full hash) into `out`.
__noinline__ __device__ void sha512(const unsigned char *data, int data_len, unsigned char out[64]) {
    // Pad into 128-byte block (big-endian)
    unsigned char block[128];
    for (int i = 0; i < data_len; i++) block[i] = data[i];
    block[data_len] = 0x80;
    for (int i = data_len + 1; i < 120; i++) block[i] = 0;
    // Length in bits as big-endian 128-bit (top 64 bits zero for small inputs)
    unsigned long long bitlen = (unsigned long long)data_len * 8;
    for (int i = 0; i < 8; i++) block[120 + i] = 0;
    for (int i = 0; i < 8; i++) block[120 + i] = (unsigned char)(bitlen >> (56 - 8*i));

    // Parse block into 16 big-endian 64-bit words
    unsigned long long W[80];
    for (int i = 0; i < 16; i++) {
        W[i] = 0;
        for (int j = 0; j < 8; j++)
            W[i] = (W[i] << 8) | block[i*8 + j];
    }
    for (int i = 16; i < 80; i++)
        W[i] = SHA512_s1(W[i-2]) + W[i-7] + SHA512_s0(W[i-15]) + W[i-16];

    // Initial hash values
    unsigned long long a = 0x6a09e667f3bcc908ULL;
    unsigned long long b = 0xbb67ae8584caa73bULL;
    unsigned long long c = 0x3c6ef372fe94f82bULL;
    unsigned long long d = 0xa54ff53a5f1d36f1ULL;
    unsigned long long e = 0x510e527fade682d1ULL;
    unsigned long long f = 0x9b05688c2b3e6c1fULL;
    unsigned long long g = 0x1f83d9abfb41bd6bULL;
    unsigned long long h = 0x5be0cd19137e2179ULL;

    for (int i = 0; i < 80; i++) {
        unsigned long long T1 = h + SHA512_S1(e) + SHA512_CH(e,f,g) + SHA512_K[i] + W[i];
        unsigned long long T2 = SHA512_S0(a) + SHA512_MAJ(a,b,c);
        h = g; g = f; f = e; e = d + T1;
        d = c; c = b; b = a; a = T1 + T2;
    }

    a += 0x6a09e667f3bcc908ULL;
    b += 0xbb67ae8584caa73bULL;
    c += 0x3c6ef372fe94f82bULL;
    d += 0xa54ff53a5f1d36f1ULL;
    e += 0x510e527fade682d1ULL;
    f += 0x9b05688c2b3e6c1fULL;
    g += 0x1f83d9abfb41bd6bULL;
    h += 0x5be0cd19137e2179ULL;

    unsigned long long hh[8] = {a, b, c, d, e, f, g, h};
    for (int i = 0; i < 8; i++)
        for (int j = 0; j < 8; j++)
            out[i*8 + j] = (unsigned char)(hh[i] >> (56 - 8*j));
}

// =========================================================================
// SHA-256  (single-block: up to 55 bytes input)
// =========================================================================

__constant__ unsigned int SHA256_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

#define ROR32(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define SHA256_CH(x,y,z)  (((x) & (y)) ^ (~(x) & (z)))
#define SHA256_MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define SHA256_S0(x) (ROR32(x,2)  ^ ROR32(x,13) ^ ROR32(x,22))
#define SHA256_S1(x) (ROR32(x,6)  ^ ROR32(x,11) ^ ROR32(x,25))
#define SHA256_s0_256(x) (ROR32(x,7)  ^ ROR32(x,18) ^ ((x) >> 3))
#define SHA256_s1_256(x) (ROR32(x,17) ^ ROR32(x,19) ^ ((x) >> 10))

__noinline__ __device__ void sha256(const unsigned char *data, int data_len, unsigned char out[32]) {
    unsigned char block[64];
    for (int i = 0; i < data_len; i++) block[i] = data[i];
    block[data_len] = 0x80;
    for (int i = data_len + 1; i < 56; i++) block[i] = 0;
    unsigned long long bitlen = (unsigned long long)data_len * 8;
    for (int i = 0; i < 4; i++) block[56 + i] = 0;
    for (int i = 0; i < 4; i++) block[60 + i] = (unsigned char)(bitlen >> (24 - 8*i));

    unsigned int W[64];
    for (int i = 0; i < 16; i++) {
        W[i] = ((unsigned int)block[i*4] << 24) | ((unsigned int)block[i*4+1] << 16)
              | ((unsigned int)block[i*4+2] << 8) | (unsigned int)block[i*4+3];
    }
    for (int i = 16; i < 64; i++)
        W[i] = SHA256_s1_256(W[i-2]) + W[i-7] + SHA256_s0_256(W[i-15]) + W[i-16];

    unsigned int a = 0x6a09e667, b = 0xbb67ae85, c = 0x3c6ef372, d = 0xa54ff53a;
    unsigned int e = 0x510e527f, f = 0x9b05688c, g = 0x1f83d9ab, h = 0x5be0cd19;

    for (int i = 0; i < 64; i++) {
        unsigned int T1 = h + SHA256_S1(e) + SHA256_CH(e,f,g) + SHA256_K[i] + W[i];
        unsigned int T2 = SHA256_S0(a) + SHA256_MAJ(a,b,c);
        h = g; g = f; f = e; e = d + T1;
        d = c; c = b; b = a; a = T1 + T2;
    }

    a += 0x6a09e667; b += 0xbb67ae85; c += 0x3c6ef372; d += 0xa54ff53a;
    e += 0x510e527f; f += 0x9b05688c; g += 0x1f83d9ab; h += 0x5be0cd19;

    unsigned int hh[8] = {a, b, c, d, e, f, g, h};
    for (int i = 0; i < 8; i++)
        for (int j = 0; j < 4; j++)
            out[i*4 + j] = (unsigned char)(hh[i] >> (24 - 8*j));
}

// =========================================================================
// RIPEMD-160  (single-block: up to 55 bytes input)
// =========================================================================

#define ROL32(x, n) (((x) << (n)) | ((x) >> (32 - (n))))
#define RMD_F(x,y,z) ((x) ^ (y) ^ (z))
#define RMD_G(x,y,z) (((x) & (y)) | (~(x) & (z)))
#define RMD_H(x,y,z) (((x) | ~(y)) ^ (z))
#define RMD_I(x,y,z) (((x) & (z)) | ((y) & ~(z)))
#define RMD_J(x,y,z) ((x) ^ ((y) | ~(z)))

__noinline__ __device__ void ripemd160(const unsigned char *data, int data_len, unsigned char out[20]) {
    // Pad into 64-byte block (little-endian length)
    unsigned char block[64];
    for (int i = 0; i < data_len; i++) block[i] = data[i];
    block[data_len] = 0x80;
    for (int i = data_len + 1; i < 56; i++) block[i] = 0;
    unsigned long long bitlen = (unsigned long long)data_len * 8;
    for (int i = 0; i < 8; i++) block[56 + i] = (unsigned char)(bitlen >> (8*i));

    // Parse as 16 little-endian 32-bit words
    unsigned int X[16];
    for (int i = 0; i < 16; i++)
        X[i] = load_4(&block[i*4]);

    unsigned int al = 0x67452301, bl = 0xefcdab89, cl = 0x98badcfe, dl = 0x10325476, el = 0xc3d2e1f0;
    unsigned int ar = al, br = bl, cr = cl, dr = dl, er = el;

    // Left word selection
    const int rl[80] = {
        0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
        7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,
        3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,
        1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,
        4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13
    };
    // Right word selection
    const int rr[80] = {
        5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,
        6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,
        15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,
        8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,
        12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11
    };
    // Left rotation amounts
    const int sl[80] = {
        11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,
        7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,
        11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,
        11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,
        9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6
    };
    // Right rotation amounts
    const int sr[80] = {
        8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,
        9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,
        9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,
        15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,
        8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11
    };

    for (int j = 0; j < 80; j++) {
        unsigned int fl, fr, kl, kr;
        if (j < 16)      { fl = RMD_F(bl,cl,dl); fr = RMD_J(br,cr,dr); kl = 0x00000000; kr = 0x50a28be6; }
        else if (j < 32) { fl = RMD_G(bl,cl,dl); fr = RMD_I(br,cr,dr); kl = 0x5a827999; kr = 0x5c4dd124; }
        else if (j < 48) { fl = RMD_H(bl,cl,dl); fr = RMD_H(br,cr,dr); kl = 0x6ed9eba1; kr = 0x6d703ef3; }
        else if (j < 64) { fl = RMD_I(bl,cl,dl); fr = RMD_G(br,cr,dr); kl = 0x8f1bbcdc; kr = 0x7a6d76e9; }
        else              { fl = RMD_J(bl,cl,dl); fr = RMD_F(br,cr,dr); kl = 0xa953fd4e; kr = 0x00000000; }

        unsigned int tl = ROL32(al + fl + X[rl[j]] + kl, sl[j]) + el;
        al = el; el = dl; dl = ROL32(cl, 10); cl = bl; bl = tl;

        unsigned int tr = ROL32(ar + fr + X[rr[j]] + kr, sr[j]) + er;
        ar = er; er = dr; dr = ROL32(cr, 10); cr = br; br = tr;
    }

    unsigned int t = 0xefcdab89 + cl + dr;
    unsigned int h1 = 0x98badcfe + dl + er;
    unsigned int h2 = 0x10325476 + el + ar;
    unsigned int h3 = 0xc3d2e1f0 + al + br;
    unsigned int h4 = 0x67452301 + bl + cr;
    unsigned int h0 = t;

    // Output as little-endian bytes
    unsigned int hh[5] = {h0, h1, h2, h3, h4};
    for (int i = 0; i < 5; i++)
        for (int j = 0; j < 4; j++)
            out[i*4 + j] = (unsigned char)(hh[i] >> (8*j));
}

// =========================================================================
// GF(2^255-19) field arithmetic — 10-limb ref10 representation
// =========================================================================
// Limb widths: 26,25,26,25,26,25,26,25,26,25 (total 255 bits)
// Each limb stored in int (int32_t). Intermediates use long long (int64_t).
// =========================================================================

typedef int fe[10];

__device__ void fe_0(fe h)    { for (int i = 0; i < 10; i++) h[i] = 0; }
__device__ void fe_1(fe h)    { h[0] = 1; for (int i = 1; i < 10; i++) h[i] = 0; }
__device__ void fe_copy(fe h, const fe f) { for (int i = 0; i < 10; i++) h[i] = f[i]; }

__device__ void fe_add(fe h, const fe f, const fe g) {
    for (int i = 0; i < 10; i++) h[i] = f[i] + g[i];
}

__device__ void fe_sub(fe h, const fe f, const fe g) {
    for (int i = 0; i < 10; i++) h[i] = f[i] - g[i];
}

__device__ void fe_neg(fe h, const fe f) {
    for (int i = 0; i < 10; i++) h[i] = -f[i];
}

__noinline__ __device__ void fe_mul(fe h, const fe f, const fe g) {
    int f0=f[0],f1=f[1],f2=f[2],f3=f[3],f4=f[4];
    int f5=f[5],f6=f[6],f7=f[7],f8=f[8],f9=f[9];
    int g0=g[0],g1=g[1],g2=g[2],g3=g[3],g4=g[4];
    int g5=g[5],g6=g[6],g7=g[7],g8=g[8],g9=g[9];
    long long g1_19=19LL*g1, g2_19=19LL*g2, g3_19=19LL*g3, g4_19=19LL*g4, g5_19=19LL*g5;
    long long g6_19=19LL*g6, g7_19=19LL*g7, g8_19=19LL*g8, g9_19=19LL*g9;
    long long f1_2=2LL*f1, f3_2=2LL*f3, f5_2=2LL*f5, f7_2=2LL*f7, f9_2=2LL*f9;

    long long h0 = (long long)f0*g0     + (long long)f1_2*g9_19 + (long long)f2*g8_19   + (long long)f3_2*g7_19 + (long long)f4*g6_19   + (long long)f5_2*g5_19 + (long long)f6*g4_19   + (long long)f7_2*g3_19 + (long long)f8*g2_19   + (long long)f9_2*g1_19;
    long long h1 = (long long)f0*g1     + (long long)f1*g0      + (long long)f2*g9_19   + (long long)f3*g8_19   + (long long)f4*g7_19   + (long long)f5*g6_19   + (long long)f6*g5_19   + (long long)f7*g4_19   + (long long)f8*g3_19   + (long long)f9*g2_19;
    long long h2 = (long long)f0*g2     + (long long)f1_2*g1    + (long long)f2*g0      + (long long)f3_2*g9_19 + (long long)f4*g8_19   + (long long)f5_2*g7_19 + (long long)f6*g6_19   + (long long)f7_2*g5_19 + (long long)f8*g4_19   + (long long)f9_2*g3_19;
    long long h3 = (long long)f0*g3     + (long long)f1*g2      + (long long)f2*g1      + (long long)f3*g0      + (long long)f4*g9_19   + (long long)f5*g8_19   + (long long)f6*g7_19   + (long long)f7*g6_19   + (long long)f8*g5_19   + (long long)f9*g4_19;
    long long h4 = (long long)f0*g4     + (long long)f1_2*g3    + (long long)f2*g2      + (long long)f3_2*g1    + (long long)f4*g0      + (long long)f5_2*g9_19 + (long long)f6*g8_19   + (long long)f7_2*g7_19 + (long long)f8*g6_19   + (long long)f9_2*g5_19;
    long long h5 = (long long)f0*g5     + (long long)f1*g4      + (long long)f2*g3      + (long long)f3*g2      + (long long)f4*g1      + (long long)f5*g0      + (long long)f6*g9_19   + (long long)f7*g8_19   + (long long)f8*g7_19   + (long long)f9*g6_19;
    long long h6 = (long long)f0*g6     + (long long)f1_2*g5    + (long long)f2*g4      + (long long)f3_2*g3    + (long long)f4*g2      + (long long)f5_2*g1    + (long long)f6*g0      + (long long)f7_2*g9_19 + (long long)f8*g8_19   + (long long)f9_2*g7_19;
    long long h7 = (long long)f0*g7     + (long long)f1*g6      + (long long)f2*g5      + (long long)f3*g4      + (long long)f4*g3      + (long long)f5*g2      + (long long)f6*g1      + (long long)f7*g0      + (long long)f8*g9_19   + (long long)f9*g8_19;
    long long h8 = (long long)f0*g8     + (long long)f1_2*g7    + (long long)f2*g6      + (long long)f3_2*g5    + (long long)f4*g4      + (long long)f5_2*g3    + (long long)f6*g2      + (long long)f7_2*g1    + (long long)f8*g0      + (long long)f9_2*g9_19;
    long long h9 = (long long)f0*g9     + (long long)f1*g8      + (long long)f2*g7      + (long long)f3*g6      + (long long)f4*g5      + (long long)f5*g4      + (long long)f6*g3      + (long long)f7*g2      + (long long)f8*g1      + (long long)f9*g0;

    long long carry;
    carry = (h0 + (1LL << 25)) >> 26; h1 += carry; h0 -= carry << 26;
    carry = (h4 + (1LL << 25)) >> 26; h5 += carry; h4 -= carry << 26;
    carry = (h1 + (1LL << 24)) >> 25; h2 += carry; h1 -= carry << 25;
    carry = (h5 + (1LL << 24)) >> 25; h6 += carry; h5 -= carry << 25;
    carry = (h2 + (1LL << 25)) >> 26; h3 += carry; h2 -= carry << 26;
    carry = (h6 + (1LL << 25)) >> 26; h7 += carry; h6 -= carry << 26;
    carry = (h3 + (1LL << 24)) >> 25; h4 += carry; h3 -= carry << 25;
    carry = (h7 + (1LL << 24)) >> 25; h8 += carry; h7 -= carry << 25;
    carry = (h4 + (1LL << 25)) >> 26; h5 += carry; h4 -= carry << 26;
    carry = (h8 + (1LL << 25)) >> 26; h9 += carry; h8 -= carry << 26;
    carry = (h9 + (1LL << 24)) >> 25; h0 += carry * 19; h9 -= carry << 25;
    carry = (h0 + (1LL << 25)) >> 26; h1 += carry; h0 -= carry << 26;

    h[0]=(int)h0; h[1]=(int)h1; h[2]=(int)h2; h[3]=(int)h3; h[4]=(int)h4;
    h[5]=(int)h5; h[6]=(int)h6; h[7]=(int)h7; h[8]=(int)h8; h[9]=(int)h9;
}

__noinline__ __device__ void fe_sq(fe h, const fe f) {
    int f0=f[0],f1=f[1],f2=f[2],f3=f[3],f4=f[4];
    int f5=f[5],f6=f[6],f7=f[7],f8=f[8],f9=f[9];
    long long f0_2=2LL*f0, f1_2=2LL*f1, f2_2=2LL*f2, f3_2=2LL*f3, f4_2=2LL*f4;
    long long f5_2=2LL*f5, f6_2=2LL*f6, f7_2=2LL*f7;
    long long f5_38=38LL*f5, f6_19=19LL*f6, f7_38=38LL*f7, f8_19=19LL*f8, f9_38=38LL*f9;

    long long h0 = (long long)f0*f0     + (long long)f1_2*f9_38 + (long long)f2_2*f8_19 + (long long)f3_2*f7_38 + (long long)f4_2*f6_19 + (long long)f5*f5_38;
    long long h1 = (long long)f0_2*f1   + (long long)f2*f9_38   + (long long)f3_2*f8_19 + (long long)f4*f7_38   + (long long)f5_2*f6_19;
    long long h2 = (long long)f0_2*f2   + (long long)f1_2*f1    + (long long)f3_2*f9_38 + (long long)f4_2*f8_19 + (long long)f5_2*f7_38 + (long long)f6*f6_19;
    long long h3 = (long long)f0_2*f3   + (long long)f1_2*f2    + (long long)f4*f9_38   + (long long)f5_2*f8_19 + (long long)f6*f7_38;
    long long h4 = (long long)f0_2*f4   + (long long)f1_2*f3_2  + (long long)f2*f2      + (long long)f5_2*f9_38 + (long long)f6_2*f8_19 + (long long)f7*f7_38;
    long long h5 = (long long)f0_2*f5   + (long long)f1_2*f4    + (long long)f2_2*f3    + (long long)f6*f9_38   + (long long)f7_2*f8_19;
    long long h6 = (long long)f0_2*f6   + (long long)f1_2*f5_2  + (long long)f2_2*f4    + (long long)f3_2*f3    + (long long)f7_2*f9_38 + (long long)f8*f8_19;
    long long h7 = (long long)f0_2*f7   + (long long)f1_2*f6    + (long long)f2_2*f5    + (long long)f3_2*f4    + (long long)f8*f9_38;
    long long h8 = (long long)f0_2*f8   + (long long)f1_2*f7_2  + (long long)f2_2*f6    + (long long)f3_2*f5_2  + (long long)f4*f4      + (long long)f9*f9_38;
    long long h9 = (long long)f0_2*f9   + (long long)f1_2*f8    + (long long)f2_2*f7    + (long long)f3_2*f6    + (long long)f4_2*f5;

    long long carry;
    carry = (h0 + (1LL << 25)) >> 26; h1 += carry; h0 -= carry << 26;
    carry = (h4 + (1LL << 25)) >> 26; h5 += carry; h4 -= carry << 26;
    carry = (h1 + (1LL << 24)) >> 25; h2 += carry; h1 -= carry << 25;
    carry = (h5 + (1LL << 24)) >> 25; h6 += carry; h5 -= carry << 25;
    carry = (h2 + (1LL << 25)) >> 26; h3 += carry; h2 -= carry << 26;
    carry = (h6 + (1LL << 25)) >> 26; h7 += carry; h6 -= carry << 26;
    carry = (h3 + (1LL << 24)) >> 25; h4 += carry; h3 -= carry << 25;
    carry = (h7 + (1LL << 24)) >> 25; h8 += carry; h7 -= carry << 25;
    carry = (h4 + (1LL << 25)) >> 26; h5 += carry; h4 -= carry << 26;
    carry = (h8 + (1LL << 25)) >> 26; h9 += carry; h8 -= carry << 26;
    carry = (h9 + (1LL << 24)) >> 25; h0 += carry * 19; h9 -= carry << 25;
    carry = (h0 + (1LL << 25)) >> 26; h1 += carry; h0 -= carry << 26;

    h[0]=(int)h0; h[1]=(int)h1; h[2]=(int)h2; h[3]=(int)h3; h[4]=(int)h4;
    h[5]=(int)h5; h[6]=(int)h6; h[7]=(int)h7; h[8]=(int)h8; h[9]=(int)h9;
}

__noinline__ __device__ void fe_invert(fe out, const fe z) {
    fe t0, t1, t2, t3;
    int i;
    fe_sq(t0, z);                                     // t0 = z^2
    fe_sq(t1, t0); fe_sq(t1, t1);                     // t1 = z^8
    fe_mul(t1, z, t1);                                // t1 = z^9
    fe_mul(t0, t0, t1);                               // t0 = z^11
    fe_sq(t2, t0);                                     // t2 = z^22
    fe_mul(t1, t1, t2);                               // t1 = z^31 = z^(2^5-1)
    fe_sq(t2, t1); for (i=1;i<5;i++) fe_sq(t2,t2);   // t2 = z^(2^10-2^5)
    fe_mul(t1, t2, t1);                               // t1 = z^(2^10-1)
    fe_sq(t2, t1); for (i=1;i<10;i++) fe_sq(t2,t2);  // t2 = z^(2^20-2^10)
    fe_mul(t2, t2, t1);                               // t2 = z^(2^20-1)
    fe_sq(t3, t2); for (i=1;i<20;i++) fe_sq(t3,t3);  // t3 = z^(2^40-2^20)
    fe_mul(t2, t3, t2);                               // t2 = z^(2^40-1)
    fe_sq(t2, t2); for (i=1;i<10;i++) fe_sq(t2,t2);  // t2 = z^(2^50-2^10)
    fe_mul(t1, t2, t1);                               // t1 = z^(2^50-1)
    fe_sq(t2, t1); for (i=1;i<50;i++) fe_sq(t2,t2);  // t2 = z^(2^100-2^50)
    fe_mul(t2, t2, t1);                               // t2 = z^(2^100-1)
    fe_sq(t3, t2); for (i=1;i<100;i++) fe_sq(t3,t3); // t3 = z^(2^200-2^100)
    fe_mul(t2, t3, t2);                               // t2 = z^(2^200-1)
    fe_sq(t2, t2); for (i=1;i<50;i++) fe_sq(t2,t2);  // t2 = z^(2^250-2^50)
    fe_mul(t1, t2, t1);                               // t1 = z^(2^250-1)
    fe_sq(t1, t1); fe_sq(t1, t1); fe_sq(t1, t1);     // t1 = z^(2^253-8)
    fe_sq(t1, t1); fe_sq(t1, t1);                     // t1 = z^(2^255-32)
    fe_mul(out, t1, t0);                              // out = z^(2^255-21) = z^(p-2)
}

__device__ void fe_frombytes(fe h, const unsigned char *s) {
    long long h0 = load_4(s);
    long long h1 = load_3(s + 4) << 6;
    long long h2 = load_3(s + 7) << 5;
    long long h3 = load_3(s + 10) << 3;
    long long h4 = load_3(s + 13) << 2;
    long long h5 = load_4(s + 16);
    long long h6 = load_3(s + 20) << 7;
    long long h7 = load_3(s + 23) << 5;
    long long h8 = load_3(s + 26) << 4;
    long long h9 = (load_3(s + 29) & 8388607) << 2;

    long long carry;
    carry = (h9 + (1LL << 24)) >> 25; h0 += carry * 19; h9 -= carry << 25;
    carry = (h1 + (1LL << 24)) >> 25; h2 += carry; h1 -= carry << 25;
    carry = (h3 + (1LL << 24)) >> 25; h4 += carry; h3 -= carry << 25;
    carry = (h5 + (1LL << 24)) >> 25; h6 += carry; h5 -= carry << 25;
    carry = (h7 + (1LL << 24)) >> 25; h8 += carry; h7 -= carry << 25;
    carry = (h0 + (1LL << 25)) >> 26; h1 += carry; h0 -= carry << 26;
    carry = (h2 + (1LL << 25)) >> 26; h3 += carry; h2 -= carry << 26;
    carry = (h4 + (1LL << 25)) >> 26; h5 += carry; h4 -= carry << 26;
    carry = (h6 + (1LL << 25)) >> 26; h7 += carry; h6 -= carry << 26;
    carry = (h8 + (1LL << 25)) >> 26; h9 += carry; h8 -= carry << 26;

    h[0]=(int)h0; h[1]=(int)h1; h[2]=(int)h2; h[3]=(int)h3; h[4]=(int)h4;
    h[5]=(int)h5; h[6]=(int)h6; h[7]=(int)h7; h[8]=(int)h8; h[9]=(int)h9;
}

__noinline__ __device__ void fe_tobytes(unsigned char *s, const fe h_in) {
    int h0=h_in[0], h1=h_in[1], h2=h_in[2], h3=h_in[3], h4=h_in[4];
    int h5=h_in[5], h6=h_in[6], h7=h_in[7], h8=h_in[8], h9=h_in[9];
    int carry;

    // Phase 1: Normalize — make all limbs non-negative via carry propagation.
    carry = h0 >> 26; h1 += carry; h0 -= carry << 26;
    carry = h1 >> 25; h2 += carry; h1 -= carry << 25;
    carry = h2 >> 26; h3 += carry; h2 -= carry << 26;
    carry = h3 >> 25; h4 += carry; h3 -= carry << 25;
    carry = h4 >> 26; h5 += carry; h4 -= carry << 26;
    carry = h5 >> 25; h6 += carry; h5 -= carry << 25;
    carry = h6 >> 26; h7 += carry; h6 -= carry << 26;
    carry = h7 >> 25; h8 += carry; h7 -= carry << 25;
    carry = h8 >> 26; h9 += carry; h8 -= carry << 26;
    carry = h9 >> 25; h0 += carry * 19; h9 -= carry << 25;
    carry = h0 >> 26; h1 += carry; h0 -= carry << 26;

    // Phase 2: Reduce mod p using tentative addition of 19.
    // If value >= p (= 2^255-19), then value+19 >= 2^255 and overflows bit 255.
    // We add 19, propagate with masking, and check the overflow.
    int t0=h0+19, t1=h1, t2=h2, t3=h3, t4=h4, t5=h5, t6=h6, t7=h7, t8=h8, t9=h9;
    carry = t0 >> 26; t1 += carry; t0 &= 0x3ffffff;
    carry = t1 >> 25; t2 += carry; t1 &= 0x1ffffff;
    carry = t2 >> 26; t3 += carry; t2 &= 0x3ffffff;
    carry = t3 >> 25; t4 += carry; t3 &= 0x1ffffff;
    carry = t4 >> 26; t5 += carry; t4 &= 0x3ffffff;
    carry = t5 >> 25; t6 += carry; t5 &= 0x1ffffff;
    carry = t6 >> 26; t7 += carry; t6 &= 0x3ffffff;
    carry = t7 >> 25; t8 += carry; t7 &= 0x1ffffff;
    carry = t8 >> 26; t9 += carry; t8 &= 0x3ffffff;
    carry = t9 >> 25; t9 &= 0x1ffffff;

    // carry=1 means value >= p: use t[] (reduced). carry=0: use h[] (original).
    int mask = carry - 1;  // 0 if carry=1, -1 (all 1s) if carry=0
    // Select: result = carry ? t : h  →  result = (t & ~mask) | (h & mask)
    h0 = (t0 & ~mask) | (h0 & mask);
    h1 = (t1 & ~mask) | (h1 & mask);
    h2 = (t2 & ~mask) | (h2 & mask);
    h3 = (t3 & ~mask) | (h3 & mask);
    h4 = (t4 & ~mask) | (h4 & mask);
    h5 = (t5 & ~mask) | (h5 & mask);
    h6 = (t6 & ~mask) | (h6 & mask);
    h7 = (t7 & ~mask) | (h7 & mask);
    h8 = (t8 & ~mask) | (h8 & mask);
    h9 = (t9 & ~mask) | (h9 & mask);

    s[0]  = (unsigned char)(h0 >> 0);
    s[1]  = (unsigned char)(h0 >> 8);
    s[2]  = (unsigned char)(h0 >> 16);
    s[3]  = (unsigned char)((h0 >> 24) | (h1 << 2));
    s[4]  = (unsigned char)(h1 >> 6);
    s[5]  = (unsigned char)(h1 >> 14);
    s[6]  = (unsigned char)((h1 >> 22) | (h2 << 3));
    s[7]  = (unsigned char)(h2 >> 5);
    s[8]  = (unsigned char)(h2 >> 13);
    s[9]  = (unsigned char)((h2 >> 21) | (h3 << 5));
    s[10] = (unsigned char)(h3 >> 3);
    s[11] = (unsigned char)(h3 >> 11);
    s[12] = (unsigned char)((h3 >> 19) | (h4 << 6));
    s[13] = (unsigned char)(h4 >> 2);
    s[14] = (unsigned char)(h4 >> 10);
    s[15] = (unsigned char)(h4 >> 18);
    s[16] = (unsigned char)(h5 >> 0);
    s[17] = (unsigned char)(h5 >> 8);
    s[18] = (unsigned char)(h5 >> 16);
    s[19] = (unsigned char)((h5 >> 24) | (h6 << 1));
    s[20] = (unsigned char)(h6 >> 7);
    s[21] = (unsigned char)(h6 >> 15);
    s[22] = (unsigned char)((h6 >> 23) | (h7 << 3));
    s[23] = (unsigned char)(h7 >> 5);
    s[24] = (unsigned char)(h7 >> 13);
    s[25] = (unsigned char)((h7 >> 21) | (h8 << 4));
    s[26] = (unsigned char)(h8 >> 4);
    s[27] = (unsigned char)(h8 >> 12);
    s[28] = (unsigned char)((h8 >> 20) | (h9 << 6));
    s[29] = (unsigned char)(h9 >> 2);
    s[30] = (unsigned char)(h9 >> 10);
    s[31] = (unsigned char)(h9 >> 18);
}

__device__ int fe_isnegative(const fe f) {
    unsigned char s[32];
    fe_tobytes(s, f);
    return s[0] & 1;
}

// =========================================================================
// Ed25519 point operations — extended coordinates (X:Y:Z:T)
// Curve: -x^2 + y^2 = 1 + d*x^2*y^2  (a = -1)
// =========================================================================

// Ed25519 basepoint (10-limb representation, computed from known coordinates)
__constant__ int BASE_X[10] = {52811034,25909283,16144682,17082669,27570973,30858332,40966398,8378388,20764389,8758491};
__constant__ int BASE_Y[10] = {40265304,26843545,13421772,20132659,26843545,6710886,53687091,13421772,40265318,26843545};
__constant__ int CURVE_D[10] = {56195235,13857412,51736253,6949390,114729,24766616,60832955,30306712,48412415,21499315};

// Point doubling: add-2008-hwcd for a=-1
// Input/output: extended coordinates (X,Y,Z,T)
__noinline__ __device__ void ge_double(fe RX, fe RY, fe RZ, fe RT,
                          const fe PX, const fe PY, const fe PZ) {
    fe A, B, C, D, E, F, G, H, t;
    fe_sq(A, PX);                       // A = X1^2
    fe_sq(B, PY);                       // B = Y1^2
    fe_sq(C, PZ); fe_add(C, C, C);     // C = 2*Z1^2
    fe_neg(D, A);                       // D = -A (since a=-1)
    fe_add(t, PX, PY); fe_sq(E, t);
    fe_sub(E, E, A); fe_sub(E, E, B);  // E = (X1+Y1)^2 - A - B
    fe_add(G, D, B);                    // G = D + B
    fe_sub(F, G, C);                    // F = G - C
    fe_sub(H, D, B);                    // H = D - B
    fe_mul(RX, E, F);                   // X3 = E*F
    fe_mul(RY, G, H);                   // Y3 = G*H
    fe_mul(RT, E, H);                   // T3 = E*H
    fe_mul(RZ, F, G);                   // Z3 = F*G
}

// Point addition: add-2008-hwcd-4 for a=-1
__noinline__ __device__ void ge_add(fe RX, fe RY, fe RZ, fe RT,
                       const fe P1X, const fe P1Y, const fe P1Z, const fe P1T,
                       const fe P2X, const fe P2Y, const fe P2Z, const fe P2T) {
    fe A, B, C, D, E, F, G, H, t, t2;
    fe_mul(A, P1X, P2X);               // A = X1*X2
    fe_mul(B, P1Y, P2Y);               // B = Y1*Y2
    fe_mul(C, P1T, P2T);
    fe_copy(t, (const int*)CURVE_D);
    fe_mul(C, C, t);                    // C = T1*d*T2
    fe_mul(D, P1Z, P2Z);               // D = Z1*Z2
    fe_add(t, P1X, P1Y);
    fe_add(t2, P2X, P2Y);
    fe_mul(E, t, t2);
    fe_sub(E, E, A); fe_sub(E, E, B);  // E = (X1+Y1)*(X2+Y2)-A-B
    fe_sub(F, D, C);                    // F = D - C
    fe_add(G, D, C);                    // G = D + C
    fe_add(H, B, A);                    // H = B + A  (since a=-1: B - a*A = B+A)
    fe_mul(RX, E, F);                   // X3 = E*F
    fe_mul(RY, G, H);                   // Y3 = G*H
    fe_mul(RT, E, H);                   // T3 = E*H
    fe_mul(RZ, F, G);                   // Z3 = F*G
}

// Scalar * Basepoint multiplication (double-and-add, MSB first)
// scalar: 32 bytes, little-endian (already clamped)
__noinline__ __device__ void ge_scalarmult_base(fe RX, fe RY, fe RZ, fe RT,
                                                const unsigned char scalar[32]) {
    // Identity point (0:1:1:0)
    fe_0(RX); fe_1(RY); fe_1(RZ); fe_0(RT);

    // Basepoint in extended coords
    fe BX, BY, BZ, BT;
    fe_copy(BX, (const int*)BASE_X);
    fe_copy(BY, (const int*)BASE_Y);
    fe_1(BZ);
    fe_mul(BT, BX, BY);  // T = X*Y/Z = X*Y (since Z=1)

    // Process from bit 254 down to 0
    for (int bit = 254; bit >= 0; bit--) {
        // Double
        fe nX, nY, nZ, nT;
        ge_double(nX, nY, nZ, nT, RX, RY, RZ);
        fe_copy(RX, nX); fe_copy(RY, nY); fe_copy(RZ, nZ); fe_copy(RT, nT);

        // Conditional add
        int byte_idx = bit >> 3;
        int bit_idx = bit & 7;
        if ((scalar[byte_idx] >> bit_idx) & 1) {
            ge_add(nX, nY, nZ, nT, RX, RY, RZ, RT, BX, BY, BZ, BT);
            fe_copy(RX, nX); fe_copy(RY, nY); fe_copy(RZ, nZ); fe_copy(RT, nT);
        }
    }
}

// Encode point to 32-byte compressed form
__noinline__ __device__ void ge_tobytes(unsigned char s[32],
                                        const fe X, const fe Y, const fe Z) {
    fe recip, x, y;
    fe_invert(recip, Z);
    fe_mul(x, X, recip);
    fe_mul(y, Y, recip);
    // Compute sign bit of x BEFORE encoding y, to avoid stack pressure issues.
    // fe_isnegative inlines fe_tobytes which is stack-heavy; doing it first
    // ensures x's memory isn't clobbered by the second fe_tobytes call.
    int x_sign = fe_isnegative(x);
    fe_tobytes(s, y);
    s[31] ^= (unsigned char)(x_sign << 7);
}

// =========================================================================
// Main kernel: ed25519 account generation
// =========================================================================
// Per thread: entropy(16B) -> SHA512Half -> seed(32B) -> SHA512 -> clamp
//             -> scalar*B -> pubkey(32B) -> SHA256(0xED||pk) -> RIPEMD160
//             -> account_id(20B)
// =========================================================================

// =========================================================================
// Base58Check encoding (XRP alphabet)
// =========================================================================

__constant__ char XRP_ALPHABET[] = "rpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65jkm8oFqi1tuvAxyz";

// SHA-256 double-hash for base58check checksum (single-block inputs up to 55 bytes)
__device__ void sha256d_checksum(const unsigned char *data, int data_len, unsigned char chk[4]) {
    unsigned char h1[32], h2[32];
    sha256(data, data_len, h1);
    sha256(h1, 32, h2);
    chk[0] = h2[0]; chk[1] = h2[1]; chk[2] = h2[2]; chk[3] = h2[3];
}

// Base58 encode a byte array. Returns the number of characters written.
// out must have room for at least max_out bytes.
__noinline__ __device__ int base58_encode(const unsigned char *input, int input_len,
                             char *out, int max_out) {
    // Count leading zeros → map to alphabet[0] ('r')
    int zeros = 0;
    while (zeros < input_len && input[zeros] == 0) zeros++;

    // Working buffer for base-58 digits (LSB first)
    unsigned char buf[50];
    int buf_len = 0;

    for (int i = zeros; i < input_len; i++) {
        int carry = input[i];
        for (int j = 0; j < buf_len; j++) {
            carry += 256 * (int)buf[j];
            buf[j] = (unsigned char)(carry % 58);
            carry /= 58;
        }
        while (carry > 0) {
            buf[buf_len++] = (unsigned char)(carry % 58);
            carry /= 58;
        }
    }

    // Build output: leading zeros + reversed digits
    int idx = 0;
    for (int i = 0; i < zeros && idx < max_out; i++)
        out[idx++] = XRP_ALPHABET[0];
    for (int i = buf_len - 1; i >= 0 && idx < max_out; i--)
        out[idx++] = XRP_ALPHABET[buf[i]];
    return idx;
}

// Encode a 16-byte ed25519 seed as an XRPL base58 seed string ("sEd...")
// Returns string length.
__device__ int encode_xrpl_seed_ed25519(const unsigned char *entropy16, char *out) {
    unsigned char versioned[23];
    // Ed25519 version bytes: 0x01, 0xE1, 0x4B
    versioned[0] = 0x01; versioned[1] = 0xE1; versioned[2] = 0x4B;
    for (int i = 0; i < 16; i++) versioned[3 + i] = entropy16[i];
    // Checksum
    unsigned char chk[4];
    sha256d_checksum(versioned, 19, chk);
    versioned[19] = chk[0]; versioned[20] = chk[1]; versioned[21] = chk[2]; versioned[22] = chk[3];
    return base58_encode(versioned, 23, out, 40);
}

// Encode a 20-byte account ID as an XRPL classic address ("r...")
// Returns string length.
__device__ int encode_xrpl_address(const unsigned char *account_id20, char *out) {
    unsigned char versioned[25];
    versioned[0] = 0x00;  // XRPL account version byte
    for (int i = 0; i < 20; i++) versioned[1 + i] = account_id20[i];
    unsigned char chk[4];
    sha256d_checksum(versioned, 21, chk);
    versioned[21] = chk[0]; versioned[22] = chk[1]; versioned[23] = chk[2]; versioned[24] = chk[3];
    return base58_encode(versioned, 25, out, 40);
}

// =========================================================================
// Main kernel: full ed25519 account generation with base58 output
// =========================================================================

// =========================================================================
// XRPL ledger index computation (SHA512-Half with namespace prefix)
// =========================================================================

// SHA512-Half: first 32 bytes of SHA-512, output as uppercase hex (64 chars)
__noinline__ __device__ void sha512_half_hex(const unsigned char *data, int data_len,
                                char *hex_out) {
    unsigned char hash[64];
    sha512(data, data_len, hash);
    const char hex_chars[] = "0123456789ABCDEF";
    for (int i = 0; i < 32; i++) {
        hex_out[i*2]     = hex_chars[hash[i] >> 4];
        hex_out[i*2 + 1] = hex_chars[hash[i] & 0x0F];
    }
}

// account_root_index = SHA512Half(0x0061 + account_id) -> 64-char hex
__device__ void compute_account_root_index(const unsigned char *acct_id,
                                           char *hex_out) {
    unsigned char preimage[22];
    preimage[0] = 0x00; preimage[1] = 0x61;  // ACCOUNT namespace
    for (int i = 0; i < 20; i++) preimage[2 + i] = acct_id[i];
    sha512_half_hex(preimage, 22, hex_out);
}

// owner_dir_index = SHA512Half(0x004F + account_id) -> 64-char hex
__device__ void compute_owner_dir_index(const unsigned char *acct_id,
                                        char *hex_out) {
    unsigned char preimage[22];
    preimage[0] = 0x00; preimage[1] = 0x4F;  // OWNER_DIR namespace
    for (int i = 0; i < 20; i++) preimage[2 + i] = acct_id[i];
    sha512_half_hex(preimage, 22, hex_out);
}

// =========================================================================
// Main kernel: full account generation + index computation + base58 output
// =========================================================================

extern "C" __global__ void generate_ed25519_accounts(
    const unsigned char* __restrict__ entropy,        // n * 16 bytes
    char* __restrict__ seed_strings,                   // n * 40 bytes (null-terminated)
    char* __restrict__ addr_strings,                   // n * 40 bytes (null-terminated)
    unsigned char* __restrict__ account_ids,           // n * 20 bytes (raw)
    char* __restrict__ account_root_indices,           // n * 64 bytes (hex, not null-terminated)
    char* __restrict__ owner_dir_indices,              // n * 64 bytes (hex, not null-terminated)
    int n
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    const unsigned char *my_entropy = entropy + idx * 16;
    char *my_seed_str = seed_strings + idx * 40;
    char *my_addr_str = addr_strings + idx * 40;
    unsigned char *my_acct_id = account_ids + idx * 20;
    char *my_acct_root_idx = account_root_indices + idx * 64;
    char *my_owner_dir_idx = owner_dir_indices + idx * 64;

    // 1. SHA-512(entropy) -> first 32 bytes = ed25519 seed
    unsigned char hash64[64];
    sha512(my_entropy, 16, hash64);
    unsigned char seed[32];
    for (int i = 0; i < 32; i++) seed[i] = hash64[i];

    // 2. SHA-512(seed) -> first 32 bytes = raw scalar
    sha512(seed, 32, hash64);

    // 3. Clamp scalar (ed25519 standard)
    unsigned char scalar[32];
    for (int i = 0; i < 32; i++) scalar[i] = hash64[i];
    scalar[0] &= 248;
    scalar[31] &= 127;
    scalar[31] |= 64;

    // 4. scalar * BasePoint -> public key
    fe RX, RY, RZ, RT;
    ge_scalarmult_base(RX, RY, RZ, RT, scalar);
    unsigned char pubkey[32];
    ge_tobytes(pubkey, RX, RY, RZ);

    // 5. Account ID = RIPEMD160(SHA256(0xED || pubkey))
    unsigned char prefixed[33];
    prefixed[0] = 0xED;
    for (int i = 0; i < 32; i++) prefixed[i+1] = pubkey[i];
    unsigned char sha_out[32];
    sha256(prefixed, 33, sha_out);
    unsigned char acct_id[20];
    ripemd160(sha_out, 32, acct_id);

    // 6. Output raw account ID (for downstream use without base58 round-trip)
    for (int i = 0; i < 20; i++) my_acct_id[i] = acct_id[i];

    // 7. Compute ledger indices while we still have the raw account ID
    compute_account_root_index(acct_id, my_acct_root_idx);
    compute_owner_dir_index(acct_id, my_owner_dir_idx);

    // 8. Base58Check encode seed and address
    int seed_len = encode_xrpl_seed_ed25519(my_entropy, my_seed_str);
    my_seed_str[seed_len] = '\0';

    int addr_len = encode_xrpl_address(acct_id, my_addr_str);
    my_addr_str[addr_len] = '\0';
}
