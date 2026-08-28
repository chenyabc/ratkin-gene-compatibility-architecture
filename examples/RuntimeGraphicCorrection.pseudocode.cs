// Conceptual pseudocode only.
// The types and APIs are intentionally incomplete and fictional.

Graphic CorrectFinalGraphic(PawnLike pawn, AddonNodeLike node, Graphic original)
{
    if (!CompatibilityScope.IsTargetPawn(pawn))
        return original;

    if (!CompatibilityScope.IsTargetEarOrTail(node))
        return original;

    Optional<ColorPair> expected = ColorPolicy.TryResolveExpectedColors(pawn, node);
    if (!expected.HasValue)
        return original;

    if (GraphicPolicy.AlreadyMatches(original, expected.Value))
        return original;

    // Preserve the upstream texture, shader, draw size and variant choice.
    // Only the conflicting color dimension is replaced.
    return GraphicPolicy.TryRecolor(original, expected.Value) ?? original;
}

void OnRelevantLifecycleBoundary(WorldLike world)
{
    foreach (PawnLike pawn in world.RelevantPawnsOnly())
    {
        if (CompatibilityScope.IsTargetPawn(pawn))
            GraphicsCache.MarkDirty(pawn);
    }
}
