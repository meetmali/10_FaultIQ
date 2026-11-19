using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FaultIQ.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddFaultEventReview : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "review_note",
                table: "fault_events",
                type: "character varying(1000)",
                maxLength: 1000,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "review_status",
                table: "fault_events",
                type: "character varying(20)",
                maxLength: 20,
                nullable: false,
                defaultValue: "unreviewed");

            migrationBuilder.AddColumn<DateTimeOffset>(
                name: "reviewed_at",
                table: "fault_events",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.AddCheckConstraint(
                name: "ck_fault_events_review_status",
                table: "fault_events",
                sql: "review_status IN ('unreviewed', 'needs_review', 'confirmed', 'rejected')");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "ck_fault_events_review_status",
                table: "fault_events");

            migrationBuilder.DropColumn(
                name: "review_note",
                table: "fault_events");

            migrationBuilder.DropColumn(
                name: "review_status",
                table: "fault_events");

            migrationBuilder.DropColumn(
                name: "reviewed_at",
                table: "fault_events");
        }
    }
}
