import java.nio.file.*;
public class ConstantFile {
 public static void main(String[] args) throws Exception {
  Path root = Paths.get(args[0]).toAbsolutePath().normalize();
  Path p = root.resolve("inside.txt");
  System.out.print(new String(Files.readAllBytes(p), "UTF-8"));
 }
}
