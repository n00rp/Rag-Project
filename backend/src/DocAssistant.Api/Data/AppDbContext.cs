using DocAssistant.Api.Domain;
using Microsoft.EntityFrameworkCore;

namespace DocAssistant.Api.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options)
{
    public DbSet<Document> Documents => Set<Document>();
    public DbSet<ChatMessage> ChatMessages => Set<ChatMessage>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Document>(e =>
        {
            e.Property(x => x.OwnerId).HasMaxLength(100);
            e.Property(x => x.FileName).HasMaxLength(255);
            e.Property(x => x.Error).HasMaxLength(1000);
            e.Property(x => x.Status).HasConversion<string>().HasMaxLength(20);
            e.HasIndex(x => new { x.OwnerId, x.CreatedAt });
        });

        b.Entity<ChatMessage>(e =>
        {
            e.Property(x => x.OwnerId).HasMaxLength(100);
            e.Property(x => x.Question).HasMaxLength(2000);
            e.Property(x => x.SourcesJson).HasColumnType("jsonb");
            e.HasIndex(x => new { x.OwnerId, x.CreatedAt });
        });
    }
}
