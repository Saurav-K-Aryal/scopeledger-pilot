import java.nio.file.*;
public class FileJoin {
 public static void main(String[] args) throws Exception {
  Path root = Paths.get(args[0]).toAbsolutePath().normalize();
  Path p = new java.io.File(args[0], args[1]).toPath();
  System.out.print(new String(Files.readAllBytes(p), "UTF-8"));
 }
}
