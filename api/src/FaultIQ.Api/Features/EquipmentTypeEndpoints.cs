namespace FaultIQ.Api.Features;

/// <summary>An equipment type FaultIQ diagnoses now ("available") or plans to ("coming_soon").</summary>
public sealed record EquipmentTypeResponse(string Id, string Name, string Status, string Description);

public static class EquipmentTypeEndpoints
{
    // The catalogue lives here, in one place (ADR 0026). Adding a type means adding its models,
    // point mappings and fault library entries, then flipping its status.
    public static readonly EquipmentTypeResponse[] Types =
    [
        new("rtu", "Rooftop units", "available", "Packaged rooftop units: refrigerant circuit, economizer and sensors."),
        new("ahu", "Air handling units", "coming_soon", "Built-up air handlers: economizer, coils, fans and sensors."),
        new("vav", "VAV boxes / terminal units", "coming_soon", "Terminal dampers, reheat and airflow."),
        new("chiller", "Chillers and cooling towers", "coming_soon", "Central plant cooling."),
        new("boiler", "Boilers and heat pumps", "coming_soon", "Heating plant and electrified heating."),
    ];

    public static RouteGroupBuilder MapEquipmentTypeEndpoints(this RouteGroupBuilder api)
    {
        api.MapGet("/equipment-types", () => TypedResults.Ok(Types))
            .WithTags("equipment-types").WithName("ListEquipmentTypes");
        return api;
    }
}
