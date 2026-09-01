using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using UAssetAPI;

// Independent reference-table dumper for issue #633 golden files.
// Usage: dotnet run -- <input.uasset> <output.golden.json>
if (args.Length != 2)
{
    Console.Error.WriteLine("usage: golden_dump <input.uasset> <output.golden.json>");
    return 1;
}

string input = args[0];
string output = args[1];

var asset = new UAsset(input);

// --- DependsMap: raw FPackageIndex int32 rows per export (UE ObjectReader.cpp) ---
var dependsRows = new JsonObject();
long dependsTotal = 0;
if (asset.DependsMap != null)
{
    for (int i = 0; i < asset.DependsMap.Count; i++)
    {
        int[] row = asset.DependsMap[i];
        dependsTotal += row.Length;
        if (row.Length > 0)
        {
            dependsRows[i.ToString()] = JsonSerializer.SerializeToNode(row);
        }
    }
}

// --- Preload dependencies: per-export spans, four UE blocks in serialization order ---
var preloadSpans = new JsonObject();
long preloadTotal = 0;
for (int i = 0; i < asset.Exports.Count; i++)
{
    var e = asset.Exports[i];
    var combined = e.SerializationBeforeSerializationDependencies
        .Concat(e.CreateBeforeSerializationDependencies)
        .Concat(e.SerializationBeforeCreateDependencies)
        .Concat(e.CreateBeforeCreateDependencies)
        .Select(x => x.Index)
        .ToList();
    preloadTotal += combined.Count;
    if (combined.Count > 0)
    {
        preloadSpans[i.ToString()] = JsonSerializer.SerializeToNode(combined);
    }
}

string sha256;
using (var stream = File.OpenRead(input))
{
    sha256 = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
}

var assembly = typeof(UAsset).Assembly;
var informational = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion
    ?? assembly.GetName().Version?.ToString() ?? "unknown";

var root = new JsonObject
{
    ["schema_version"] = 1,
    ["provenance"] = new JsonObject
    {
        ["generator"] = "UAssetAPI",
        ["generator_version"] = informational,
        ["runtime"] = $".NET {Environment.Version} / {RuntimeInformation.OSDescription}",
        ["produced_utc"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
        ["invocation"] = "dotnet run --project tests/samples/golden/dumper -- <fixture> <output>",
    },
    ["fixture"] = new JsonObject
    {
        ["name"] = Path.GetFileName(input),
        ["sha256"] = sha256,
        ["size_bytes"] = new FileInfo(input).Length,
    },
    ["counts"] = new JsonObject
    {
        ["name"] = asset.GetNameMapIndexList().Count,
        ["import"] = asset.Imports?.Count ?? 0,
        ["export"] = asset.Exports.Count,
    },
    ["depends_map"] = new JsonObject
    {
        ["total_edges"] = dependsTotal,
        ["rows"] = dependsRows,
    },
    ["preload"] = new JsonObject
    {
        ["total_entries"] = preloadTotal,
        ["spans"] = preloadSpans,
    },
};

// Normalize to LF: the repo stores these files via .gitattributes eol=lf, and
// regeneration must be byte-stable across platforms.
var json = root.ToJsonString(new JsonSerializerOptions
{
    WriteIndented = true,
    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
}).Replace("\r\n", "\n");
File.WriteAllText(output, json + "\n");
Console.WriteLine($"{Path.GetFileName(input)}: name={root["counts"]!["name"]} import={root["counts"]!["import"]} export={root["counts"]!["export"]} depends={dependsTotal} preload={preloadTotal} -> {output}");
return 0;
