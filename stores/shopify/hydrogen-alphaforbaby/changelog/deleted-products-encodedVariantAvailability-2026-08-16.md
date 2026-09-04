# Deleted products — encodedVariantAvailability bug (2026-08-16)

**Context:** 3 products stuck permanently unable to sell — `encodedVariantAvailability`
(Storefront API, Shopify's own combinatorial availability index, `@inContext(country: US)`
matching the live site's actual query) was empty (`"v1_"`, just the version prefix, no data)
while `encodedVariantExistence` was fully populated and real CJ stock existed. Confirmed via
a 14-day audit of all 34 active products that no others show this — see chat history
2026-08-16 for the full investigation (diagnostic methodology, no-op reindex attempt,
Shopify community-forum precedent for this exact field going wrong). A trivial no-op
`productVariantsBulkUpdate` (re-setting each variant's existing price) was applied to try to
force Shopify to reindex — confirmed ineffective after 12 checks over ~6 minutes
(06:24–06:30 UTC), so these were deleted rather than left live and permanently un-buyable.

Logged here in full in case we want to re-source the same products fresh (new Shopify
product, same CJ supplier item) later — a fresh product typically gets a fresh index entry
rather than inheriting whatever corrupted this one.

---

## 1. Little Chef Play Set ("Lace-Trimmed Chef Outfit for Babies")

- **Shopify product ID:** `gid://shopify/Product/7628225740871`
- **Handle:** `lace-trimmed-chef-outfit-for-babies`
- **CJ supplier product ID:** `2608090817191636800`
- **Vendor:** ALPHA FOR BABY · **Collection:** Baby Girls
- **SEO description:** Spark your child's imagination with a kitchen adventure they'll return to again and again.

**Variants (4, option: Color):**

| SKU (= CJ variant id) | Color | Price | Compare-at |
|---|---|---|---|
| 2608090817191637900 | Blue | $12.90 | $16.90 |
| 2608090817191638400 | Pink | $12.90 | $16.90 |
| 2608090817191637400 | Red | $12.90 | $16.90 |
| 2608090817191638900 | White | $12.90 | $16.90 |

**Images:**
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/99f551af-c90b-4aaf-b77c-aae52a3da1b4.jpg (White)
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/d6af9ee8-b6c0-4848-8ba7-0d8939131833.jpg
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/22804e88-0c80-4831-99f8-bbce6a3538b5.jpg (Red)
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/bc0d8d67-ac1f-40e4-bbdf-868b24f85ca1.jpg (Pink)
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/8b4d3024-c12c-4535-a2a1-c9699bc0fb0f.jpg (Blue)

---

## 2. Girls Cozy Pajama Set ("Girls' Breathable Pajama Set")

- **Shopify product ID:** `gid://shopify/Product/7629469548615`
- **Handle:** `girls-breathable-pajama-set`
- **CJ supplier product ID:** `2607290434211633700`
- **Vendor:** ALPHA FOR BABY · **Collection:** Baby Girls
- **SEO description:** Bedtime just got sweeter with a set so soft, she'll actually want to go to sleep.

**Variants (76, options: Color × Size 73/80/90/100cm) — price by color:**

| Color | Price | Compare-at | Example SKU |
|---|---|---|---|
| Be Careful Of The Full Print | $30.90 | $41.90 | 2607290434251630300 |
| small mushroom | $30.90 | — | (no SKU on file — CJ variant id missing) |
| polka dot duck | $30.90 | — | (no SKU on file) |
| pink rabbit | $30.90 | — | (no SKU on file) |
| pink heart | $33.90 | $45.90 | 2607290434221634900 |
| pink flower | $33.90 | $45.90 | 2607290434231638000 |
| green flower | $35.90 | $47.90 | 2607290434231631500 |
| yellow duck | $30.90 | — | (no SKU on file) |
| yellow heart | $30.90 | — | (no SKU on file) |
| yellow flower | $30.90 | — | (no SKU on file) |
| white flower | $30.90 | — | (no SKU on file) |
| all over flower | $30.90 | $41.90 | 2607290434251635600 |
| all over star | $27.90 | $37.90 | 2607290434231633900 |
| all over polka dot | $30.90 | $41.90 | 2607290434231633400 |
| all over heart | $33.90 | $45.90 | 2607290434221636800 |
| all over floral | $30.90 | $41.90 | 2607290434261630700 |
| cute rabbit | $33.90 | $45.90 | 2607290434221633500 |
| floral rabbit | $37.90 | $50.90 | 2607290434221631500 |
| cute strawberry | $37.90 | $50.90 | 2607290434261633400 |
| cute polka dot | $37.90 | $50.90 | 2607290434241639200 |

Full 76-row variant table (every color × size combo with its Shopify variant GID and SKU)
is preserved in the chat/tool-call history for this session if ever needed at that
granularity — trimmed here to one row per color for readability. ~40% of variants have no
CJ variant-id SKU recorded (a pre-existing data gap on this product, unrelated to the
availability bug).

**Images (20):**
- white flower: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/58fc2cf8-a65b-49cb-b321-d16dd6f58617_fine.jpg
- all over star: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/c2fb9c40-d4ec-4d22-8660-558cfc26a690_fine.jpg
- polka dot duck: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/5f92b2fb-6609-429b-8077-cb9e92d4a94f_fine.jpg
- yellow duck: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/10449c34-c5f3-4fab-a61a-919b54184086_fine.jpg
- yellow flower: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/88bfd78d-a135-4750-bc09-fd2a4bd82637_fine.jpg
- all over floral: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/08d549fc-822c-41cb-9570-5bbe9c83d18c_fine.jpg
- pink heart: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/94415cd5-0c9d-457e-b906-b6bb905b47bd_fine.jpg
- all over heart: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/77a9afab-049c-40d0-b102-ca995d959c60_fine.jpg
- (unnamed): https://cdn.shopify.com/s/files/1/0686/0993/3383/files/7ad1b479-1b67-4be8-ba32-f6c87e49bcc3_fine.jpg
- floral rabbit: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/7ab69aeb-5fb1-49d7-8e44-43e7b9a2aeb3_fine.jpg
- yellow heart: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/f9d3663e-d455-42ca-a418-247b85e39a61_fine.jpg
- cute strawberry: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/74dce71c-cd7d-4fa2-b24a-a0e67079b21e_fine.jpg
- all over flower: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/a81734d9-a724-4152-8e54-3f310b63a28b_fine.jpg
- pink flower: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/0dcaa605-e943-4ec2-b7c1-60d6561ee4dd_fine.jpg
- cute polka dot: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/097d4845-eb30-490c-9ba2-148b82998b8f_fine.jpg
- Be Careful Of The Full Print: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/e371f06e-4f0d-415a-92d4-fdcb01a40553_fine.jpg
- cute rabbit: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/1671dce4-72c3-46a9-a7a7-818bc13f6e08_fine.jpg
- pink rabbit: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/49595783-d1c4-41aa-9f0c-a1ad142de632_fine.jpg
- green flower: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/65ec4c3a-274c-4809-83f1-84ecb8486a52_fine.jpg
- all over polka dot: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/15e0e1e0-97f8-40c2-9f12-2ae7d1d27d4f_fine.jpg
- small mushroom: https://cdn.shopify.com/s/files/1/0686/0993/3383/files/1af2d61c-71c8-4bca-a6e1-c7ab0688121d_fine.jpg

---

## 3. Toddler Cozy Fall Set ("Chic Toddler Fall Set")

- **Shopify product ID:** `gid://shopify/Product/7630897086535`
- **Handle:** `chic-toddler-fall-set`
- **CJ supplier product ID:** `2607240314561635200`
- **Vendor:** ALPHA FOR BABY · **Collection:** Baby Girls
- **SEO description:** Keep your little one warm, stylish, and ready for every autumn adventure.

**Variants (6, option: Size):**

| SKU (= CJ variant id) | Size | Price | Compare-at |
|---|---|---|---|
| 2607240314561636000 | 100cm | $11.90 | $15.90 |
| 2607240314561636600 | 110cm | $11.90 | $15.90 |
| 2607240314561637100 | 120cm | $11.90 | $15.90 |
| 2607240314561637700 | 130cm | $11.90 | $15.90 |
| 2607240314561638400 | 140cm | $11.90 | $15.90 |
| 2607240314561638900 | 150cm | $11.90 | $15.90 |

**Images (5):**
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/b4aef603-34cb-4c9a-b695-90924690cc77.jpg
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/fa138e6f-67bf-45be-aabe-abb254f5b228.jpg
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/be697af3-0c8b-40dc-8673-f4982040dc98.jpg
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/78044bd6-43e6-4232-bea1-424ab22574bb.jpg
- https://cdn.shopify.com/s/files/1/0686/0993/3383/files/93b20940-58a9-44b0-b8cb-4d5ac62172ce_fine.jpg
