using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FaultIQ.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class InitialSchema : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "equipment",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    site = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_equipment", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "uploads",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    equipment_id = table.Column<Guid>(type: "uuid", nullable: false),
                    original_name = table.Column<string>(type: "character varying(255)", maxLength: 255, nullable: false),
                    stored_name = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    format = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    size_bytes = table.Column<long>(type: "bigint", nullable: false),
                    sha256 = table.Column<string>(type: "character(64)", fixedLength: true, maxLength: 64, nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_uploads", x => x.id);
                    table.CheckConstraint("ck_uploads_format", "format IN ('lbnl_simulated', 'lbnl_experimental')");
                    table.CheckConstraint("ck_uploads_size_bytes", "size_bytes > 0");
                    table.ForeignKey(
                        name: "fk_uploads_equipment_equipment_id",
                        column: x => x.equipment_id,
                        principalTable: "equipment",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "analyses",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    upload_id = table.Column<Guid>(type: "uuid", nullable: false),
                    equipment_id = table.Column<Guid>(type: "uuid", nullable: false),
                    point_set = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    status = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    attempts = table.Column<int>(type: "integer", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    started_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    finished_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    worker_id = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: true),
                    traceparent = table.Column<string>(type: "character varying(55)", maxLength: 55, nullable: true),
                    error_code = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: true),
                    error_message = table.Column<string>(type: "character varying(1000)", maxLength: 1000, nullable: true),
                    pipeline_version = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: true),
                    model_version = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: true),
                    hours_total = table.Column<int>(type: "integer", nullable: true),
                    hours_scored = table.Column<int>(type: "integer", nullable: true),
                    hours_alarmed = table.Column<int>(type: "integer", nullable: true),
                    event_count = table.Column<int>(type: "integer", nullable: true),
                    result = table.Column<string>(type: "jsonb", nullable: true),
                    chart_series = table.Column<string>(type: "jsonb", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_analyses", x => x.id);
                    table.CheckConstraint("ck_analyses_attempts", "attempts >= 0");
                    table.CheckConstraint("ck_analyses_point_set", "point_set IN ('all', 'basic')");
                    table.CheckConstraint("ck_analyses_status", "status IN ('queued', 'running', 'succeeded', 'failed')");
                    table.ForeignKey(
                        name: "fk_analyses_equipment_equipment_id",
                        column: x => x.equipment_id,
                        principalTable: "equipment",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "fk_analyses_uploads_upload_id",
                        column: x => x.upload_id,
                        principalTable: "uploads",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "fault_events",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    analysis_id = table.Column<Guid>(type: "uuid", nullable: false),
                    equipment_id = table.Column<Guid>(type: "uuid", nullable: false),
                    event_key = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    kind = table.Column<string>(type: "character varying(30)", maxLength: 30, nullable: false),
                    fault = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: true),
                    starts_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    ends_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false),
                    hours = table.Column<int>(type: "integer", nullable: false),
                    confidence = table.Column<double>(type: "double precision", nullable: true),
                    detector_score = table.Column<double>(type: "double precision", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_fault_events", x => x.id);
                    table.CheckConstraint("ck_fault_events_hours", "hours > 0");
                    table.CheckConstraint("ck_fault_events_kind", "kind IN ('fault', 'inconclusive', 'no_supported_fault', 'not_diagnosable')");
                    table.CheckConstraint("ck_fault_events_span", "ends_at > starts_at");
                    table.ForeignKey(
                        name: "fk_fault_events_analyses_analysis_id",
                        column: x => x.analysis_id,
                        principalTable: "analyses",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_fault_events_equipment_equipment_id",
                        column: x => x.equipment_id,
                        principalTable: "equipment",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "ix_analyses_equipment_id_created_at",
                table: "analyses",
                columns: new[] { "equipment_id", "created_at" });

            migrationBuilder.CreateIndex(
                name: "ix_analyses_status_created_at",
                table: "analyses",
                columns: new[] { "status", "created_at" });

            migrationBuilder.CreateIndex(
                name: "ix_analyses_upload_id",
                table: "analyses",
                column: "upload_id");

            migrationBuilder.CreateIndex(
                name: "ix_equipment_site",
                table: "equipment",
                column: "site");

            migrationBuilder.CreateIndex(
                name: "ix_fault_events_analysis_id_event_key",
                table: "fault_events",
                columns: new[] { "analysis_id", "event_key" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_fault_events_equipment_id_starts_at",
                table: "fault_events",
                columns: new[] { "equipment_id", "starts_at" });

            migrationBuilder.CreateIndex(
                name: "ix_fault_events_fault_starts_at",
                table: "fault_events",
                columns: new[] { "fault", "starts_at" });

            migrationBuilder.CreateIndex(
                name: "ix_uploads_equipment_id",
                table: "uploads",
                column: "equipment_id");

            migrationBuilder.CreateIndex(
                name: "ix_uploads_sha256",
                table: "uploads",
                column: "sha256");

            migrationBuilder.CreateIndex(
                name: "ix_uploads_stored_name",
                table: "uploads",
                column: "stored_name",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "fault_events");

            migrationBuilder.DropTable(
                name: "analyses");

            migrationBuilder.DropTable(
                name: "uploads");

            migrationBuilder.DropTable(
                name: "equipment");
        }
    }
}
