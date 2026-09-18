# The rewrite principles moved

The principles now live with the lenses, one set per lens, because what a line should say
instead depends on what kind of writing it is. A pitch and a contract clause do not want
the same sentence.

| Lens | File |
|---|---|
| `marketing` (the default) | [`lenses/marketing.md`](../lenses/marketing.md) |
| `business-eval` | [`lenses/business-eval.md`](../lenses/business-eval.md) |
| `legal` | [`lenses/legal.md`](../lenses/legal.md) |
| `editorial` | [`lenses/editorial.md`](../lenses/editorial.md) |

The five principles that used to sit in this file are the marketing set, and `marketing`
is what you get when you do not ask for a lens. To write your own, copy
[`lenses/_template.md`](../lenses/_template.md).

## The rule above all five, under every lens

**Never invent proof.** No customer counts, no testimonials, no ratings the business has
not earned. Where a build needs a proof slot it does not have, say so on the page:

> **Before:** ~~Loved by 10,000+ happy homeowners~~
> **After:** Project names and photography are placeholders — swap in your own jobs before this goes live.

No lens relaxes this. `allow_proof: true` in a lint block silences the regex, not the rule.
